import os
from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.core.management import call_command
from django.template import Context, Template
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.companies.admin import LinkAdmin
from core.companies.forms import CompanyForm, LinkForm
from core.companies.models import Company, CompanyType, Link, Product
from core.companies.parser import create_firefox_driver
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

    def test_product_save_links_post_when_post_title_is_inside_product_name(self):
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
                "name": "Яблуня Ред Чіф контейнер",
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
            name="Саджанець яблуні Фуджі",
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
            "link": "//article/a/@href",
        }

        form = LinkForm(instance=self.source)

        self.assertNotIn("parser_map", form.fields)
        self.assertEqual(form.fields["parser_name_xpath"].initial, "//article/h2/text()")
        self.assertEqual(form.fields["parser_price_xpath"].initial, "//article/span/text()")
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
