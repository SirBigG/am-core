import os
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import Mock, patch

import requests
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.companies.admin import LinkAdmin
from core.companies.forms import CompanyForm, LinkForm
from core.companies.management.commands.run_local_parser_worker import Command as LocalParserWorkerCommand
from core.companies.management.commands.run_local_parser_worker import ParserWorkerClient
from core.companies.models import Company, CompanyType, Link, Product, ProductMatchRule, assess_product_post
from core.companies.parser import create_firefox_driver, extract_price, get_content_from_url, parse_data_from_content
from core.utils.tests.factories import CategoryFactory, LocationFactory, PostFactory, UserFactory


class CompanyParserDriverTests(SimpleTestCase):
    @patch("core.companies.parser.webdriver.Firefox")
    @patch("core.companies.parser.FirefoxService")
    def test_firefox_driver_uses_configured_system_geckodriver(self, service_class, firefox_class):
        service = object()
        service_class.return_value = service

        with patch.dict(os.environ, {"GECKODRIVER_PATH": "/custom/geckodriver"}):
            driver = create_firefox_driver()

        service_class.assert_called_once_with(executable_path="/custom/geckodriver")
        self.assertEqual(firefox_class.call_args.kwargs["service"], service)
        self.assertEqual(driver, firefox_class.return_value)


class CompanyParserExtractionTests(SimpleTestCase):
    @patch("core.companies.parser.requests.get")
    def test_static_fetch_uses_source_friendly_request_headers(self, get):
        get.return_value.status_code = 200
        get.return_value.content = b"<html></html>"

        get_content_from_url("https://shop.example/products")

        headers = get.call_args.kwargs["headers"]
        self.assertIn("AgroMegaParser", headers["User-Agent"])
        self.assertTrue(headers["Accept-Language"].startswith("uk-UA"))

    def test_item_scoped_xpath_keeps_products_aligned_when_optional_price_is_missing(self):
        products = parse_data_from_content(
            (
                "<section>"
                "<article><h2>Golden apple</h2><span>42,50 грн</span></article>"
                "<article><h2>Gala apple</h2></article>"
                "</section>"
            ),
            {"item": "//article", "name": ".//h2/text()", "price": ".//span/text()"},
        )

        self.assertEqual(
            products,
            [
                {"name": "Golden apple", "price": 42.5},
                {"name": "Gala apple", "price": None},
            ],
        )

    def test_legacy_xpath_rejects_misaligned_nonempty_field_lists(self):
        with self.assertRaisesRegex(ValueError, "result count mismatch"):
            parse_data_from_content(
                "<article><h2>A</h2><span>10</span></article><article><h2>B</h2></article>",
                {"name": "//h2/text()", "price": "//span/text()"},
            )

    def test_price_parser_supports_spaces_and_decimal_comma(self):
        self.assertEqual(extract_price("1 234,56 грн"), 1234.56)


class ParserWorkerClientTests(SimpleTestCase):
    def test_result_submission_retries_transport_failure_with_same_payload(self):
        client = ParserWorkerClient("https://agromega.example", "token", timeout=10, submit_retries=1)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"count": 1}'
        response.url = "https://agromega.example/api/parser/sources/10/results/"
        client.session.post = Mock(side_effect=[requests.ConnectionError("response lost"), response])

        result = client.submit_results(
            10,
            "00000000-0000-0000-0000-000000000001",
            [{"name": "Golden apple"}],
            snapshot_complete=True,
        )

        self.assertEqual(result, {"count": 1})
        self.assertEqual(client.session.post.call_count, 2)
        first_payload = client.session.post.call_args_list[0].kwargs["json"]
        second_payload = client.session.post.call_args_list[1].kwargs["json"]
        self.assertEqual(first_payload, second_payload)

    def test_failure_submission_retries_transport_failure_with_same_payload(self):
        client = ParserWorkerClient("https://agromega.example", "token", timeout=10, submit_retries=1)
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"status": "recorded", "replayed": true}'
        response.url = "https://agromega.example/api/parser/sources/10/failure/"
        client.session.post = Mock(side_effect=[requests.ConnectionError("response lost"), response])

        result = client.submit_failure(
            10,
            "00000000-0000-0000-0000-000000000001",
            "Remote timeout",
            status=503,
        )

        self.assertTrue(result["replayed"])
        self.assertEqual(client.session.post.call_count, 2)
        first_payload = client.session.post.call_args_list[0].kwargs["json"]
        second_payload = client.session.post.call_args_list[1].kwargs["json"]
        self.assertEqual(first_payload, second_payload)


class CompanyPublicViewTests(TestCase):
    def setUp(self):
        self.location = LocationFactory()
        self.company = Company.objects.create(
            name="Agro Shop",
            type=CompanyType.SHOP,
            description="Seeds and tools",
            active=True,
            website="https://shop.example.com",
            location=self.location,
        )

    def test_company_list_renders_active_shops(self):
        Company.objects.create(
            name="Inactive Shop",
            type=CompanyType.SHOP,
            description="Hidden",
            active=False,
            website="https://hidden.example.com",
            location=self.location,
        )
        Company.objects.create(
            name="Service Company",
            type=CompanyType.SERVICE,
            description="Service",
            active=True,
            website="https://service.example.com",
            location=self.location,
        )

        response = self.client.get(reverse("companies:list"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "companies/list.html")
        self.assertEqual(list(response.context["companies"]), [self.company])

    def test_company_list_uses_uncropped_logo_style(self):
        self.company.logo = "companies/company-logo.png"
        self.company.save(update_fields=["logo"])

        response = self.client.get(reverse("companies:list"))

        self.assertContains(response, "site-company-card__header")
        self.assertContains(response, "site-company-card__logo")

    def test_company_detail_uses_uncropped_logo_style(self):
        self.company.logo = "companies/company-logo.png"
        self.company.save(update_fields=["logo"])

        response = self.client.get(self.company.get_absolute_url())

        self.assertContains(response, "company-logo-frame")
        self.assertContains(response, "company-logo-frame__image")

    def test_company_detail_renders_products(self):
        product = Product.objects.create(
            company=self.company,
            name="Corn seed",
            description="Hybrid seed",
            price="100.00",
            price_updated_at=timezone.now(),
        )

        response = self.client.get(self.company.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "companies/detail.html")
        self.assertEqual(response.context["company"], self.company)
        self.assertIn(product, response.context["products"])
        self.assertContains(response, "site-detail-panel")
        self.assertContains(response, "site-product-card")
        self.assertContains(response, "100,00")

    def test_company_detail_marks_stale_price_without_hiding_product(self):
        Product.objects.create(
            company=self.company,
            name="Old apple",
            description="Stored apple",
            price="100.00",
            price_updated_at=timezone.now() - timedelta(days=31),
        )

        response = self.client.get(self.company.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Old apple")
        self.assertContains(response, "Ціна потребує оновлення.")

    def test_products_for_post_hides_stale_price(self):
        post = PostFactory()
        Product.objects.create(
            company=self.company,
            post=post,
            name="Fresh apple",
            price="20.00",
            price_updated_at=timezone.now(),
        )
        Product.objects.create(
            company=self.company,
            post=post,
            name="Stale apple",
            price="30.00",
            price_updated_at=timezone.now() - timedelta(days=31),
        )

        rendered = Template("{% load companies_extras %}{% products_for_post post.id %}").render(
            Context({"post": post})
        )

        self.assertIn("Fresh apple", rendered)
        self.assertIn("20,00", rendered)
        self.assertIn("Stale apple", rendered)
        self.assertNotIn("30,00", rendered)

    def test_product_save_refreshes_price_updated_at_when_price_changes(self):
        old_timestamp = timezone.now() - timedelta(days=31)
        product = Product.objects.create(
            company=self.company,
            name="Admin apple",
            price="10.00",
            price_updated_at=old_timestamp,
        )
        product.price = "12.00"

        product.save(update_fields={"price"})

        product.refresh_from_db()
        self.assertEqual(product.price, 12)
        self.assertGreater(product.price_updated_at, old_timestamp)

    def test_product_save_requires_review_for_partial_name(self):
        category = CategoryFactory(slug="apple-varieties", value="Сорти яблунь")
        post = PostFactory(
            rubric=category,
            title="Голден Делішес",
            text="Опис сорту яблуні Голден Делішес.",
        )

        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Саджанець яблуні Голден Делішес дворічний",
            price="120.00",
        )

        self.assertEqual(product.post, post)
        self.assertEqual(product.match_status, Product.MatchStatus.REVIEW)
        self.assertIn(post.title, product.match_reason)

    def test_product_save_does_not_link_post_from_other_category(self):
        post = PostFactory(
            title="Голден Делішес",
            text="Опис сорту яблуні Голден Делішес.",
        )
        other_category = CategoryFactory(slug="pear-varieties", value="Сорти груш")

        product = Product.objects.create(
            company=self.company,
            category=other_category,
            name="Саджанець яблуні Голден Делішес дворічний",
            price="120.00",
        )

        self.assertNotEqual(product.post, post)
        self.assertIsNone(product.post)

    def test_product_update_or_create_persists_auto_linked_post(self):
        category = CategoryFactory(slug="apple-seedlings", value="Саджанці яблуні")
        post = PostFactory(
            rubric=category,
            title="Ред Чіф",
            text="Опис сорту яблуні Ред Чіф.",
        )

        product, _created = Product.objects.update_or_create(
            company=self.company,
            source_product_key="red-chief",
            defaults={
                "category": category,
                "name": "Ред Чіф",
                "price": "150.00",
            },
        )

        product.refresh_from_db()
        self.assertEqual(product.post, post)

    def test_link_product_posts_command_backfills_existing_unlinked_products(self):
        category = CategoryFactory(slug="apple-backfill", value="Сорти яблунь")
        product = Product.objects.create(
            company=self.company,
            category=category,
            name="Фуджі",
            price="130.00",
        )
        post = PostFactory(
            rubric=category,
            title="Фуджі",
            text="Опис сорту яблуні Фуджі.",
        )
        output = StringIO()

        call_command("link_product_posts", stdout=output)

        product.refresh_from_db()
        self.assertEqual(product.post, post)
        self.assertIn("Linked 1 of", output.getvalue())

    def test_company_detail_returns_404_for_unknown_company(self):
        response = self.client.get("/companies/missing-999.html")

        self.assertEqual(response.status_code, 404)


class ParserSourceCadenceTests(TestCase):
    def setUp(self):
        self.category = CategoryFactory()
        self.location = LocationFactory()
        self.company = Company.objects.create(
            name="Cadence Shop",
            type=CompanyType.SHOP,
            description="Seeds and tools",
            active=True,
            website="https://cadence-shop.example.com",
            location=self.location,
        )

    def test_link_defaults_to_one_day_parser_crawl_interval(self):
        source = Link.objects.create(
            url="https://cadence-shop.example.com/products",
            company=self.company,
            category=self.category,
        )

        self.assertEqual(source.crawl_interval_minutes, 1440)
        self.assertEqual(source.effective_crawl_interval_minutes(), 1440)

    def test_effective_crawl_interval_uses_global_minimum(self):
        source = Link.objects.create(
            url="https://cadence-shop.example.com/products",
            company=self.company,
            category=self.category,
            crawl_interval_minutes=30,
        )

        self.assertEqual(source.effective_crawl_interval_minutes(), 1440)


class CompanyAdminParserSafetyTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.category = CategoryFactory()
        self.location = LocationFactory()
        self.company = Company.objects.create(
            name="Admin Shop",
            type=CompanyType.SHOP,
            description="Seeds and tools",
            active=True,
            website="https://admin-shop.example.com",
            location=self.location,
        )
        self.source = Link.objects.create(
            url="https://admin-shop.example.com/products",
            company=self.company,
            category=self.category,
        )

    @override_settings(ENABLE_IN_PROCESS_COMPANY_PARSING=False)
    def test_parse_link_admin_action_hidden_when_in_process_parsing_disabled(self):
        request = self.factory.get("/admin/companies/link/")
        request.user = self.user
        model_admin = LinkAdmin(Link, admin.site)

        actions = model_admin.get_actions(request)

        self.assertNotIn("parse_link", actions)

    @override_settings(ENABLE_IN_PROCESS_COMPANY_PARSING=True)
    def test_parse_link_admin_action_available_when_enabled(self):
        request = self.factory.get("/admin/companies/link/")
        request.user = self.user
        model_admin = LinkAdmin(Link, admin.site)

        actions = model_admin.get_actions(request)

        self.assertIn("parse_link", actions)

    def test_link_form_exposes_parser_map_as_minimal_structured_fields(self):
        self.source.parser_map = {
            "name": "//article/h2/text()",
            "price": "//article/span/text()",
            "min_price": "//article/span[1]/text()",
            "max_price": "//article/span[last()]/text()",
            "link": "//article/a/@href",
            "max_pages": 3,
            "next_page": "//a[@rel='next']/@href",
        }

        form = LinkForm(instance=self.source)

        self.assertNotIn("parser_map", form.fields)
        self.assertEqual(form.fields["parser_name_xpath"].initial, "//article/h2/text()")
        self.assertEqual(form.fields["parser_price_xpath"].initial, "//article/span/text()")
        self.assertEqual(form.fields["parser_min_price_xpath"].initial, "//article/span[1]/text()")
        self.assertEqual(form.fields["parser_max_price_xpath"].initial, "//article/span[last()]/text()")
        self.assertEqual(form.fields["parser_link_xpath"].initial, "//article/a/@href")
        self.assertFalse(form.fields["parser_snapshot_complete"].initial)
        self.assertEqual(form.fields["parser_next_page_xpath"].initial, "//a[@rel='next']/@href")
        self.assertEqual(form.fields["parser_max_pages"].initial, 3)
        self.assertEqual(form.fields["parser_name_xpath"].widget.attrs["rows"], 3)

    def test_link_form_saves_structured_parser_map_and_preserves_extra_keys(self):
        self.source.parser_map = {"link": "//article/a/@href"}
        data = {
            "url": self.source.url,
            "company": self.company.pk,
            "category": self.category.pk,
            "source_type": Link.SOURCE_TYPE_STATIC,
            "experiment_label": self.source.experiment_label,
            "parser_config_version": self.source.parser_config_version,
            "priority": self.source.priority,
            "crawl_interval_minutes": self.source.crawl_interval_minutes,
            "last_product_count": self.source.last_product_count,
            "active": "on",
            "parser_name_xpath": "//article/h2/text()",
            "parser_price_xpath": "//article/span/text()",
            "parser_min_price_xpath": "//article/span[1]/text()",
            "parser_max_price_xpath": "//article/span[last()]/text()",
            "parser_link_xpath": "//article/a/@href",
            "parser_snapshot_complete": "on",
            "parser_next_page_xpath": "//a[@rel='next']/@href",
            "parser_max_pages": "3",
        }

        form = LinkForm(data=data, instance=self.source)

        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(
            saved.parser_map,
            {
                "link": "//article/a/@href",
                "name": "//article/h2/text()",
                "price": "//article/span/text()",
                "min_price": "//article/span[1]/text()",
                "max_price": "//article/span[last()]/text()",
                "snapshot_complete": True,
                "next_page": "//a[@rel='next']/@href",
                "max_pages": 3,
            },
        )

    def test_company_form_uses_structured_parser_map_fields(self):
        self.company.parser_map = {"name": "//h1/text()", "price": "//strong/text()"}
        data = {
            "name": self.company.name,
            "type": self.company.type,
            "description": self.company.description,
            "active": "on",
            "website": self.company.website,
            "location": self.location.pk,
            "latitude": "50.450100",
            "longitude": "30.523400",
            "parser_name_xpath": "//article/h2/text()",
            "parser_price_xpath": "//article/span/text()",
        }

        form = CompanyForm(data=data, instance=self.company)

        self.assertNotIn("parser_map", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.latitude, Decimal("50.450100"))
        self.assertEqual(saved.longitude, Decimal("30.523400"))
        self.assertEqual(
            saved.parser_map,
            {
                "name": "//article/h2/text()",
                "price": "//article/span/text()",
            },
        )

    def test_company_form_validates_coordinate_ranges(self):
        data = {
            "name": self.company.name,
            "type": self.company.type,
            "description": self.company.description,
            "active": "on",
            "website": self.company.website,
            "location": self.location.pk,
            "latitude": "91",
            "longitude": "181",
            "parser_name_xpath": "",
            "parser_price_xpath": "",
        }

        form = CompanyForm(data=data, instance=self.company)

        self.assertFalse(form.is_valid())
        self.assertIn("latitude", form.errors)
        self.assertIn("longitude", form.errors)

    def test_parser_map_form_requires_name_and_price_together(self):
        data = {
            "url": self.source.url,
            "company": self.company.pk,
            "category": self.category.pk,
            "source_type": Link.SOURCE_TYPE_STATIC,
            "priority": self.source.priority,
            "crawl_interval_minutes": self.source.crawl_interval_minutes,
            "last_product_count": self.source.last_product_count,
            "active": "on",
            "parser_name_xpath": "//article/h2/text()",
            "parser_price_xpath": "",
        }

        form = LinkForm(data=data, instance=self.source)

        self.assertFalse(form.is_valid())
        self.assertIn("Provide both product name and price XPath selectors.", form.errors["__all__"])


class LocalParserWorkerCommandTests(SimpleTestCase):
    @patch("core.companies.management.commands.run_local_parser_worker.get_content_from_url")
    def test_static_source_follows_configured_pagination(self, get_content):
        get_content.side_effect = [
            '<article><h2>Golden</h2></article><a rel="next" href="/apples/page/2">Next</a>',
            "<article><h2>Gala</h2></article>",
        ]
        source = {
            "id": 10,
            "url": "https://shop.example.com/apples",
            "source_type": "static",
            "parser_map": {
                "item": "//article",
                "name": ".//h2/text()",
                "next_page": "//a[@rel='next']/@href",
                "max_pages": 3,
            },
        }

        products, driver = LocalParserWorkerCommand().parse_source(source)

        self.assertIsNone(driver)
        self.assertEqual([product["name"] for product in products], ["Golden", "Gala"])
        self.assertEqual(
            [call.args[0] for call in get_content.call_args_list],
            ["https://shop.example.com/apples", "https://shop.example.com/apples/page/2"],
        )

    @patch("core.companies.management.commands.run_local_parser_worker.get_content_from_url")
    @patch("core.companies.management.commands.run_local_parser_worker.ParserWorkerClient")
    def test_worker_leases_static_source_and_submits_results(self, client_class, get_content_from_url):
        client = client_class.return_value
        client.list_sources.return_value = [
            {
                "id": 10,
                "url": "https://shop.example.com/apples",
                "source_type": "static",
                "parser_map": {
                    "name": "//article/h2/text()",
                    "price": "//article/span/text()",
                    "link": "//article/a/@href",
                },
            }
        ]
        client.lease.return_value = {"lease_token": "00000000-0000-0000-0000-000000000001"}
        get_content_from_url.return_value = """
            <article>
                <h2>Golden apple</h2>
                <span>42.50 грн</span>
                <a href="https://shop.example.com/apples/golden">Details</a>
            </article>
        """

        output = StringIO()
        call_command("run_local_parser_worker", "--token", "token-value", stdout=output)

        client.list_sources.assert_called_once_with(category=None, experiment=None, limit=5)
        client.lease.assert_called_once_with(10, 30)
        client.submit_results.assert_called_once()
        submitted_products = client.submit_results.call_args.args[2]
        self.assertEqual(submitted_products[0]["name"], "Golden apple")
        self.assertEqual(submitted_products[0]["product_url"], "https://shop.example.com/apples/golden")
        self.assertEqual(submitted_products[0]["price"], 42.50)
        self.assertIn("Submitted 1 products", output.getvalue())

    @patch("core.companies.management.commands.run_local_parser_worker.get_content_from_url")
    @patch("core.companies.management.commands.run_local_parser_worker.ParserWorkerClient")
    def test_worker_records_failure_after_lease(self, client_class, get_content_from_url):
        client = client_class.return_value
        client.list_sources.return_value = [
            {
                "id": 11,
                "url": "https://shop.example.com/apples",
                "source_type": "static",
                "parser_map": {"name": "//h2/text()"},
            }
        ]
        client.lease.return_value = {"lease_token": "00000000-0000-0000-0000-000000000002"}
        get_content_from_url.side_effect = ValueError("Remote timeout")

        call_command("run_local_parser_worker", "--token", "token-value", stderr=StringIO())

        client.submit_failure.assert_called_once()
        self.assertEqual(client.submit_failure.call_args.args[:2], (11, "00000000-0000-0000-0000-000000000002"))

    @patch("core.companies.management.commands.run_local_parser_worker.get_content_from_url")
    @patch("core.companies.management.commands.run_local_parser_worker.ParserWorkerClient")
    def test_worker_does_not_report_parser_failure_when_result_submit_is_uncertain(
        self, client_class, get_content_from_url
    ):
        client = client_class.return_value
        client.list_sources.return_value = [
            {
                "id": 12,
                "url": "https://shop.example.com/apples",
                "source_type": "static",
                "parser_map": {
                    "name": "//article/h2/text()",
                    "price": "//article/span/text()",
                },
            }
        ]
        client.lease.return_value = {"lease_token": "00000000-0000-0000-0000-000000000003"}
        client.submit_results.side_effect = ValueError("connection dropped after submit")
        get_content_from_url.return_value = """
            <article>
                <h2>Golden apple</h2>
                <span>42.50 грн</span>
            </article>
        """
        stderr = StringIO()

        call_command("run_local_parser_worker", "--token", "token-value", stderr=stderr)

        client.submit_results.assert_called_once()
        client.submit_failure.assert_not_called()
        self.assertIn("Could not confirm result submission", stderr.getvalue())

    @patch("core.companies.management.commands.run_local_parser_worker.get_content_from_url")
    @patch("core.companies.management.commands.run_local_parser_worker.ParserWorkerClient")
    def test_worker_records_server_rejected_result_as_failure(self, client_class, get_content_from_url):
        client = client_class.return_value
        client.list_sources.return_value = [
            {
                "id": 13,
                "url": "https://shop.example.com/apples",
                "source_type": "static",
                "parser_map": {
                    "name": "//article/h2/text()",
                    "price": "//article/span/text()",
                    "snapshot_complete": True,
                },
            }
        ]
        client.lease.return_value = {"lease_token": "00000000-0000-0000-0000-000000000004"}
        rejection_response = requests.Response()
        rejection_response.status_code = 400
        rejection_response._content = b'{"snapshot_complete":["A complete snapshot cannot be empty."]}'
        rejection_response.url = "https://agromega.example/api/parser/sources/13/results/"
        client.submit_results.side_effect = requests.HTTPError(response=rejection_response)
        get_content_from_url.return_value = "<html><body>No products</body></html>"
        stderr = StringIO()

        call_command("run_local_parser_worker", "--token", "token-value", stderr=stderr)

        client.submit_failure.assert_called_once()
        self.assertEqual(client.submit_failure.call_args.kwargs["status"], 400)
        self.assertIn("Recorded rejected result", stderr.getvalue())


class ProductMatchReviewTests(TestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Match shop", website="https://example.com", location=LocationFactory()
        )
        self.category = CategoryFactory()

    def product(self, name, **kwargs):
        return Product.objects.create(company=self.company, category=self.category, name=name, **kwargs)

    def test_substring_and_fulltext_do_not_create_wrong_link(self):
        PostFactory(rubric=self.category, title="Мир", text="Яблуня Симиренко", status=True)
        p = self.product("Яблуня Симиренко")
        self.assertIsNone(p.post)
        self.assertNotIn("Частковий", p.match_reason)

    def test_ambiguous_exact_titles_require_review(self):
        for _ in range(2):
            PostFactory(rubric=self.category, title="Гала", status=True)
        p = self.product("Гала")
        self.assertIsNone(p.post)
        self.assertIn("Декілька", p.match_reason)

    def test_full_name_match_and_changed_identity(self):
        post = PostFactory(rubric=self.category, title="Гала", status=True)
        p = self.product("  ГАЛА  ")
        self.assertEqual(p.post, post)
        self.assertEqual(p.match_status, Product.MatchStatus.AUTO)
        p.name = "Невідомий сорт"
        p.save(update_fields=["name"])
        p.refresh_from_db()
        self.assertIsNone(p.post)
        self.assertEqual(p.match_status, Product.MatchStatus.REVIEW)

    def test_bundle_and_sport_only_offer_suggestions(self):
        PostFactory(rubric=self.category, title="Гала", status=True)
        PostFactory(rubric=self.category, title="Флоріна", status=True)
        for name in ("Комплект Гала + Флоріна",):
            p = self.product(name)
            self.assertIsNone(p.post)
            self.assertEqual(p.match_status, Product.MatchStatus.REVIEW)

    def test_confirmed_absence_survives_ingestion_and_backfill(self):
        p = self.product("Гала", match_status=Product.MatchStatus.CONFIRMED)
        PostFactory(rubric=self.category, title="Гала", status=True)
        Product.objects.update_or_create(pk=p.pk, defaults={"name": "Гала", "price": "123.00"})
        call_command("link_product_posts", stdout=StringIO())
        p.refresh_from_db()
        self.assertIsNone(p.post)
        self.assertEqual(p.match_status, Product.MatchStatus.CONFIRMED)

    def test_manual_clear_and_manual_choice_survive_next_import(self):
        post = PostFactory(rubric=self.category, title="Гала", status=True)
        p = self.product("Гала")
        p.post = None
        p.save(update_fields=["post"])
        p.refresh_from_db()
        self.assertEqual(p.match_status, Product.MatchStatus.CONFIRMED)
        p.save()
        self.assertIsNone(p.post)
        p.post = post
        p.save(update_fields=["post"])
        Product.objects.update_or_create(pk=p.pk, defaults={"name": "Гала нова назва", "price": "150.00"})
        p.refresh_from_db()
        self.assertEqual(p.post, post)
        self.assertEqual(p.match_status, Product.MatchStatus.CONFIRMED)

    def test_admin_filters_and_confirmation_action(self):
        from core.companies.admin import ProductAdmin

        model_admin = ProductAdmin(Product, admin.site)
        self.assertIn("category", model_admin.list_filter)
        self.assertNotIn("source_link", model_admin.list_filter)
        p = self.product("Невідомий сорт")
        with patch.object(model_admin, "log_change"), patch.object(model_admin, "message_user"):
            model_admin.confirm_matches(RequestFactory().post("/"), Product.objects.filter(pk=p.pk))
        p.refresh_from_db()
        self.assertEqual(p.match_status, Product.MatchStatus.CONFIRMED)
        self.assertIsNone(p.post)

    def test_seller_title_missing_prefix_uses_distinctive_token(self):
        PostFactory(rubric=self.category, title="Мир", status=True)
        post = PostFactory(rubric=self.category, title="Ренет Симиренко", status=True)
        p = self.product("Яблуня Симиренко дворічна контейнер 5 л")
        self.assertEqual(p.post, post)
        self.assertEqual(p.match_status, Product.MatchStatus.REVIEW)

    def test_specific_cultivar_and_explicit_latin_alias(self):
        PostFactory(rubric=self.category, title="Гала", status=True)
        post = PostFactory(rubric=self.category, title="Гала Маст (Gala Mast)", status=True)
        self.assertEqual(self.product("Саджанець яблуні Гала Маст 2 роки").post, post)
        self.assertEqual(self.product("Apple Gala Mast container 5 l").post, post)

    def test_shared_generic_word_does_not_select_wrong_red_variety(self):
        PostFactory(rubric=self.category, title="Ред Топаз", status=True)
        PostFactory(rubric=self.category, title="Рояль Ред Делішес", status=True)
        self.assertIsNone(self.product("Яблуня Ред Чіф пізній сорт").post)


class ProductMatchDictionaryTests(TestCase):
    def setUp(self):
        ProductMatchRule.objects.all().delete()
        self.category = CategoryFactory()
        self.product = Product(category=self.category, name="Особливий товар")
        self.post = PostFactory(rubric=self.category, title="Особливий сорт", status=True)

    def test_admin_rule_changes_take_effect_without_restart(self):
        model_admin = admin.site._registry[ProductMatchRule]
        request = RequestFactory().get("/")
        request.user = UserFactory(is_staff=True, is_superuser=True)
        form_class = model_admin.get_form(request)
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        form = form_class(data={"word": "  ОСОБЛИВИЙ  ", "purpose": "ignore", "active": True})
        self.assertTrue(form.is_valid(), form.errors)
        rule = form.save()
        self.assertEqual(rule.word, "особливий")
        self.assertIsNone(assess_product_post(self.product)[0])
        rule.active = False
        rule.save(update_fields=["active"])
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        rule.active = True
        rule.word = "інше"
        rule.save()
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        rule.delete()
        self.assertEqual(assess_product_post(self.product)[0], self.post)

    def test_dictionary_validation_and_normalized_uniqueness(self):
        ProductMatchRule.objects.create(word="Унікальне")
        for values in (
            {"word": "УНІКАЛЬНЕ"},
            {"word": "два слова"},
            {"word": "---"},
            {"word": "слово", "prefix": True},
        ):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                ProductMatchRule(**values).full_clean()

    def test_bundle_rules_support_exact_and_prefix_and_deactivation(self):
        self.product.name = "Пакування Особливий сорт"
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        rule = ProductMatchRule.objects.create(word="пакув", purpose=ProductMatchRule.Purpose.BUNDLE)
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        rule.prefix = True
        rule.save()
        self.assertIsNone(assess_product_post(self.product)[0])
        rule.active = False
        rule.save()
        self.assertEqual(assess_product_post(self.product)[0], self.post)

    def test_empty_dictionary_has_no_hidden_bundle_words(self):
        self.product.name = "Комплект Особливий сорт"
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        self.product.name = "Особливий сорт + інший"
        self.assertIsNone(assess_product_post(self.product)[0])


class ProductMatchingAdminControlsTests(TestCase):
    def setUp(self):
        from core.companies.admin import ProductAdmin
        from core.companies.models import ProductMatchAlias

        self.alias_model = ProductMatchAlias
        self.category = CategoryFactory()
        self.other_category = CategoryFactory()
        self.post = PostFactory(rubric=self.category, title="Ренет Симиренко", status=True)
        self.company = Company.objects.create(name="Test", website="https://example.com", location=LocationFactory())
        self.product = Product.objects.create(
            name="Apple Semerenko container", category=self.category, company=self.company, price="125.00"
        )
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.model_admin = ProductAdmin(Product, admin.site)

    def action(self, data=None):
        request = RequestFactory().post("/", data or {})
        request.user = self.user
        with patch.object(self.model_admin, "message_user"):
            return self.model_admin.reassess_matches(request, Product.objects.filter(pk=self.product.pk))

    def test_alias_whole_phrase_activation_and_category(self):
        alias = self.alias_model.objects.create(name="  SEMERENKO ", post=self.post)
        self.assertEqual(alias.name, "semerenko")
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        self.product.name = "Apple xSemerenko"
        self.assertIsNone(assess_product_post(self.product)[0])
        self.product.name = "Apple Semerenko container"
        self.product.category = self.other_category
        self.assertIsNone(assess_product_post(self.product)[0])
        self.product.category = self.category
        alias.active = False
        alias.save()
        self.assertIsNone(assess_product_post(self.product)[0])
        alias.active = True
        alias.save()
        self.post.status = False
        self.post.save()
        self.assertIsNone(assess_product_post(self.product)[0])

    def test_alias_ambiguity_and_normalized_duplicates(self):
        self.alias_model.objects.create(name="Semerenko", post=self.post)
        with self.assertRaises(ValidationError):
            self.alias_model(name="SEMERENKO", post=self.post).full_clean()
        other = PostFactory(rubric=self.category, title="Інший сорт", status=True)
        self.alias_model.objects.create(name="Semerenko", post=other)
        self.assertIsNone(assess_product_post(self.product)[0])

    def test_scoped_rules_and_global_uniqueness(self):
        ProductMatchRule.objects.all().delete()
        self.product.name = "Ренет товар"
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        ProductMatchRule.objects.create(word="ренет", category=self.other_category)
        self.assertEqual(assess_product_post(self.product)[0], self.post)
        ProductMatchRule.objects.create(word="ренет", category=self.category)
        self.assertIsNone(assess_product_post(self.product)[0])
        with self.assertRaises(ValidationError):
            ProductMatchRule(word="РЕНЕТ", category=self.category).full_clean()
        ProductMatchRule.objects.create(word="ренет")
        with self.assertRaises(ValidationError):
            ProductMatchRule(word="РЕНЕТ").full_clean()

    def test_preview_and_apply_audited_without_price_or_confirmation_changes(self):
        from django.contrib.admin.models import LogEntry

        self.alias_model.objects.create(name="Semerenko", post=self.post)
        price_time = self.product.price_updated_at
        response = self.action()
        self.product.refresh_from_db()
        self.assertIsNone(self.product.post_id)
        self.assertEqual(response.context_data["rows"][0]["post_id"], self.post.pk)
        # Render the real admin template as well as checking its projection.
        self.assertIn("Застосувати зміни", response.render().content.decode())
        self.assertIsNone(self.action({"apply_matching": "1", "preview_token": response.context_data["preview_token"]}))
        self.product.refresh_from_db()
        self.assertEqual(self.product.post_id, self.post.pk)
        self.assertEqual(self.product.match_status, Product.MatchStatus.REVIEW)
        self.assertEqual(self.product.price_updated_at, price_time)
        self.assertEqual(self.product.price, Decimal("125.00"))
        self.assertEqual(LogEntry.objects.filter(user=self.user, object_id=str(self.product.pk)).count(), 1)

    def test_changed_rules_and_forged_preview_do_not_apply(self):
        alias = self.alias_model.objects.create(name="Semerenko", post=self.post)
        token = self.action().context_data["preview_token"]
        alias.active = False
        alias.save()
        self.assertIsNotNone(self.action({"apply_matching": "1", "preview_token": token}))
        self.assertIsNotNone(self.action({"apply_matching": "1", "preview_token": "forged"}))
        self.product.refresh_from_db()
        self.assertIsNone(self.product.post_id)

    def test_new_manual_confirmation_protects_against_stale_preview(self):
        self.alias_model.objects.create(name="Semerenko", post=self.post)
        token = self.action().context_data["preview_token"]
        Product.objects.filter(pk=self.product.pk).update(match_status=Product.MatchStatus.CONFIRMED)
        response = self.action({"apply_matching": "1", "preview_token": token})
        self.assertTrue(response.context_data["rows"][0]["protected"])
        self.product.refresh_from_db()
        self.assertIsNone(self.product.post_id)
        self.assertEqual(self.product.match_status, Product.MatchStatus.CONFIRMED)

    def test_change_permission_required(self):
        from django.core.exceptions import PermissionDenied

        self.user.is_superuser = False
        self.user.save()
        with self.assertRaises(PermissionDenied):
            self.action()

    def test_admin_action_roundtrip(self):
        self.alias_model.objects.create(name="Semerenko", post=self.post)
        self.client.force_login(self.user)
        url = reverse("admin:companies_product_changelist")
        data = {"action": "reassess_matches", "_selected_action": str(self.product.pk)}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        data.update(apply_matching="1", preview_token=response.context_data["preview_token"])
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.product.refresh_from_db()
        self.assertEqual(self.product.post_id, self.post.pk)

    def test_preview_is_bound_to_user_and_expires(self):
        self.alias_model.objects.create(name="Semerenko", post=self.post)
        token = self.action().context_data["preview_token"]
        self.user = UserFactory(is_staff=True, is_superuser=True)
        self.assertIsNotNone(self.action({"apply_matching": "1", "preview_token": token}))
        with patch("django.core.signing.time.time", return_value=1000):
            expired = self.action().context_data["preview_token"]
        self.assertIsNotNone(self.action({"apply_matching": "1", "preview_token": expired}))
        self.product.refresh_from_db()
        self.assertIsNone(self.product.post_id)

    def test_reassessment_can_clear_old_wrong_link(self):
        Product.objects.filter(pk=self.product.pk).update(post=self.post, match_status=Product.MatchStatus.REVIEW)
        token = self.action().context_data["preview_token"]
        self.action({"apply_matching": "1", "preview_token": token})
        self.product.refresh_from_db()
        self.assertIsNone(self.product.post_id)
        self.assertEqual(self.product.match_status, Product.MatchStatus.REVIEW)
