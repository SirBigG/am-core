from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.companies.models import Company, CompanyType, Link, ParserSourceAttempt, Product, ProductPriceHistory
from core.utils.tests.factories import CategoryFactory, LocationFactory, UserFactory

ONE_DAY_AND_ONE_MINUTE = 1441


class ParserWorkerAPITests(APITestCase):
    def setUp(self):
        self.category = CategoryFactory(slug="apples", value="Apples")
        self.location = LocationFactory()
        self.company = Company.objects.create(
            name="Apple Shop",
            type=CompanyType.SHOP,
            description="Fresh apples",
            active=True,
            website="https://shop.example.com",
            location=self.location,
        )
        self.source = Link.objects.create(
            url="https://shop.example.com/apples",
            company=self.company,
            category=self.category,
            parser_map={"name": "//h1"},
            experiment_label="apples-phase-1",
        )
        self.worker_user = UserFactory(email="parser-worker@example.com", first_name="laptop-a", last_name="")
        content_type = ContentType.objects.get_for_model(Link)
        permission = Permission.objects.get(content_type=content_type, codename="use_parser_worker_api")
        self.worker_user.user_permissions.add(permission)
        self.token = Token.objects.create(user=self.worker_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_source_cursor_loads_more_than_one_hundred_without_skipping(self):
        for i in range(101):
            Link.objects.create(url=f"https://shop.example/{i}", company=self.company, category=self.category)
        first = self.client.get("/api/parser/sources/", {"scope": "all", "limit": 100, "after_id": 0})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(len(first.data), 100)
        cursor = first.data[-1]["id"]
        Link.objects.filter(pk=first.data[0]["id"]).update(priority=999)
        second = self.client.get("/api/parser/sources/", {"scope": "all", "limit": 100, "after_id": cursor})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(len(second.data), 2)
        ids = [row["id"] for row in first.data + second.data]
        self.assertEqual(len(set(ids)), 102)
        last = self.client.get("/api/parser/sources/", {"scope": "all", "after_id": ids[-1]})
        self.assertEqual(last.data, [])

    def test_source_list_requires_parser_token(self):
        self.client.credentials()

        response = self.client.get("/api/parser/sources/")

        self.assertEqual(response.status_code, 401)

    def test_source_list_rejects_token_without_parser_permission(self):
        normal_user = UserFactory(email="normal-user@example.com")
        normal_token = Token.objects.create(user=normal_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {normal_token.key}")

        response = self.client.get("/api/parser/sources/")

        self.assertEqual(response.status_code, 403)

    def test_source_list_filters_by_category_and_experiment(self):
        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.source.id)
        self.assertEqual(response.data[0]["category_slug"], "apples")

    def test_source_list_uses_company_parser_map_when_link_map_is_empty(self):
        Company.objects.filter(pk=self.company.pk).update(parser_map={"name": "//article/h2", "price": "//span"})
        Link.objects.filter(pk=self.source.pk).update(parser_map=None)

        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["parser_map"], {"name": "//article/h2", "price": "//span"})

    def test_source_list_prefers_link_parser_map_over_company_map(self):
        Company.objects.filter(pk=self.company.pk).update(parser_map={"name": "//company/h2", "price": "//span"})
        Link.objects.filter(pk=self.source.pk).update(parser_map={"name": "//link/h2", "price": "//strong"})

        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["parser_map"], {"name": "//link/h2", "price": "//strong"})

    def test_source_catalog_scope_all_includes_not_due_and_inactive_sources(self):
        Link.objects.filter(pk=self.source.pk).update(last_crawled=timezone.now())
        inactive_source = Link.objects.create(
            url="https://shop.example.com/inactive",
            company=self.company,
            category=self.category,
            active=False,
        )

        response = self.client.get("/api/parser/sources/?scope=all&limit=100")

        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["id"] for item in response.data}, {self.source.id, inactive_source.id})

    def test_source_detail_returns_runtime_and_parser_configuration(self):
        response = self.client.get(f"/api/parser/sources/{self.source.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.source.id)
        self.assertEqual(response.data["company_name"], self.company.name)
        self.assertEqual(response.data["parser_map"], {"name": "//h1"})
        self.assertIn("is_due", response.data)
        self.assertIn("lease_active", response.data)

    def test_company_and_category_catalogs_are_paginated(self):
        company_response = self.client.get("/api/parser/companies/")
        category_response = self.client.get("/api/parser/categories/")

        self.assertEqual(company_response.status_code, 200)
        self.assertEqual(category_response.status_code, 200)
        self.assertEqual(company_response.data["results"][0]["source_count"], 1)
        self.assertEqual(category_response.data["results"][0]["id"], self.category.id)

    def test_source_list_returns_only_sources_due_for_crawl(self):
        Link.objects.filter(pk=self.source.pk).update(last_crawled=timezone.now(), crawl_interval_minutes=1440)

        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(minutes=ONE_DAY_AND_ONE_MINUTE),
            crawl_interval_minutes=1440,
        )

        due_response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(due_response.status_code, 200)
        self.assertEqual(len(due_response.data), 1)

    def test_source_list_rejects_invalid_limit(self):
        response = self.client.get("/api/parser/sources/?limit=abc")

        self.assertEqual(response.status_code, 400)
        self.assertIn("limit", response.data)

    def test_source_list_enforces_one_day_minimum_crawl_interval(self):
        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(hours=23, minutes=59),
            crawl_interval_minutes=30,
        )

        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(minutes=ONE_DAY_AND_ONE_MINUTE),
            crawl_interval_minutes=30,
        )

        due_response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(due_response.status_code, 200)
        self.assertEqual(len(due_response.data), 1)

    def test_lease_sets_worker_and_rejects_second_active_lease(self):
        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 200)
        self.assertIn("lease_token", response.data)
        self.source.refresh_from_db()
        self.assertEqual(self.source.leased_by, "laptop-a")
        self.assertTrue(self.source.leased_until > timezone.now())

        second_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(second_response.status_code, 409)

    def test_expired_lease_can_be_replaced(self):
        self.source.lease("old-worker", duration_minutes=1)
        Link.objects.filter(pk=self.source.pk).update(leased_until=timezone.now() - timedelta(minutes=1))

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.leased_by, "laptop-a")

    def test_lease_rejects_stale_list_source_that_is_no_longer_due(self):
        Link.objects.filter(pk=self.source.pk).update(last_crawled=timezone.now(), crawl_interval_minutes=1440)

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Source is not due for crawling.")
        self.source.refresh_from_db()
        self.assertIsNone(self.source.lease_token)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.lease_token)

    def test_lease_rejects_source_crawled_less_than_one_day_ago(self):
        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(hours=23, minutes=59),
            crawl_interval_minutes=30,
        )

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Source is not due for crawling.")

    def test_force_lease_requires_on_demand_permission_and_can_run_not_due_source(self):
        Link.objects.filter(pk=self.source.pk).update(last_crawled=timezone.now())

        forbidden_response = self.client.post(
            f"/api/parser/sources/{self.source.id}/lease/",
            {"duration_minutes": 15, "force": True},
        )

        self.assertEqual(forbidden_response.status_code, 403)
        permission = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Link),
            codename="run_parser_source_on_demand",
        )
        self.worker_user.user_permissions.add(permission)

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/lease/",
            {"duration_minutes": 15, "force": True},
        )

        self.assertEqual(response.status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.leased_by, "laptop-a")

    def test_lease_rejects_source_deactivated_after_listing(self):
        Link.objects.filter(pk=self.source.pk).update(active=False)

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Source is inactive.")
        self.source.refresh_from_db()
        self.assertIsNone(self.source.lease_token)

    @override_settings(PARSER_FAILURE_RETRY_MINUTES=60)
    def test_source_list_hides_recent_failures_until_retry_cooldown_expires(self):
        Link.objects.filter(pk=self.source.pk).update(last_error_at=timezone.now())

        response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

        Link.objects.filter(pk=self.source.pk).update(last_error_at=timezone.now() - timedelta(minutes=61))

        due_response = self.client.get("/api/parser/sources/?category=apples&experiment=apples-phase-1")

        self.assertEqual(due_response.status_code, 200)
        self.assertEqual(len(due_response.data), 1)

    @override_settings(PARSER_FAILURE_RETRY_MINUTES=60)
    def test_lease_rejects_recent_failure_until_retry_cooldown_expires(self):
        Link.objects.filter(pk=self.source.pk).update(last_error_at=timezone.now())

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Source is not due for crawling.")

        Link.objects.filter(pk=self.source.pk).update(last_error_at=timezone.now() - timedelta(minutes=61))

        due_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(due_response.status_code, 200)

    def test_result_submission_upserts_product_and_price_history(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        observed_at = timezone.now().isoformat()

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "description": "Sweet apple",
                        "product_url": "https://shop.example.com/apples/golden",
                        "price": "42.50",
                        "currency": "UAH",
                        "observed_at": observed_at,
                        "raw_price": "42.50 грн",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        product = Product.objects.get(source_link=self.source)
        self.assertEqual(product.name, "Golden apple")
        self.assertEqual(product.price, Decimal("42.50"))
        self.assertEqual(product.source_product_key, "https://shop.example.com/apples/golden")
        self.assertEqual(ProductPriceHistory.objects.filter(product=product).count(), 1)
        self.source.refresh_from_db()
        self.assertIsNone(self.source.lease_token)
        self.assertEqual(self.source.last_product_count, 1)

        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(minutes=ONE_DAY_AND_ONE_MINUTE),
            crawl_interval_minutes=1440,
        )
        second_lease = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        self.assertEqual(second_lease.status_code, 200)
        second_response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": second_lease.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "product_url": "https://shop.example.com/apples/golden",
                        "price": "45.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Product.objects.filter(source_link=self.source).count(), 1)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("45.00"))
        self.assertEqual(ProductPriceHistory.objects.filter(product=product).count(), 2)
        self.assertEqual(
            ParserSourceAttempt.objects.filter(
                source_link=self.source, status=ParserSourceAttempt.STATUS_SUCCESS
            ).count(),
            2,
        )

    def test_attempt_product_and_price_history_catalogs_filter_by_source(self):
        product = Product.objects.create(
            company=self.company,
            category=self.category,
            source_link=self.source,
            source_product_key="golden",
            name="Golden apple",
            price=Decimal("42.50"),
        )
        ProductPriceHistory.objects.create(
            product=product,
            source_link=self.source,
            price=Decimal("42.50"),
            observed_at=timezone.now(),
            worker_name="laptop-a",
        )
        ParserSourceAttempt.objects.create(
            source_link=self.source,
            worker_name="laptop-a",
            status=ParserSourceAttempt.STATUS_SUCCESS,
            product_count=1,
        )

        attempts = self.client.get(f"/api/parser/attempts/?source={self.source.id}")
        products = self.client.get(f"/api/parser/products/?source={self.source.id}")
        prices = self.client.get(f"/api/parser/price-history/?source={self.source.id}")

        self.assertEqual(attempts.status_code, 200)
        self.assertEqual(products.status_code, 200)
        self.assertEqual(prices.status_code, 200)
        self.assertEqual(attempts.data["results"][0]["product_count"], 1)
        self.assertEqual(products.data["results"][0]["name"], "Golden apple")
        self.assertEqual(prices.data["results"][0]["price"], "42.50")

    def test_result_submission_without_price_preserves_previous_price(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        first_response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "product_url": "https://shop.example.com/apples/golden",
                        "price": "42.50",
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(first_response.status_code, 200)
        product = Product.objects.get(source_link=self.source)
        price_updated_at = product.price_updated_at

        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(minutes=ONE_DAY_AND_ONE_MINUTE),
            crawl_interval_minutes=1440,
        )
        second_lease = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        self.assertEqual(second_lease.status_code, 200)
        second_response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": second_lease.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "product_url": "https://shop.example.com/apples/golden",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(second_response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("42.50"))
        self.assertEqual(product.price_updated_at, price_updated_at)
        self.assertEqual(ProductPriceHistory.objects.filter(product=product).count(), 1)

    def test_older_observation_is_kept_in_history_without_replacing_current_price(self):
        current_time = timezone.now() - timedelta(hours=1)
        product = Product.objects.create(
            company=self.company,
            category=self.category,
            source_link=self.source,
            source_product_key="https://shop.example.com/apples/golden",
            name="Golden apple",
            link="https://shop.example.com/apples/golden",
            price=Decimal("45.00"),
            price_updated_at=current_time,
        )
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "product_url": product.link,
                        "price": "40.00",
                        "observed_at": (current_time - timedelta(days=1)).isoformat(),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("45.00"))
        self.assertEqual(product.price_updated_at, current_time)
        self.assertTrue(ProductPriceHistory.objects.filter(product=product, price=Decimal("40.00")).exists())

    @override_settings(PARSER_MAX_FUTURE_OBSERVATION_MINUTES=5)
    def test_future_observation_is_rejected_without_consuming_lease(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [
                    {
                        "name": "Golden apple",
                        "price": "42.50",
                        "observed_at": (timezone.now() + timedelta(minutes=6)).isoformat(),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.source.refresh_from_db()
        self.assertIsNotNone(self.source.lease_token)
        self.assertFalse(Product.objects.exists())

    @override_settings(PARSER_MAX_PRODUCTS_PER_RESULT=1)
    def test_result_rejects_oversized_product_batch(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [{"name": "Golden apple"}, {"name": "Gala apple"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("products", response.data)
        self.assertFalse(Product.objects.exists())

    @override_settings(PARSER_MAX_RAW_PRODUCT_BYTES=10)
    def test_result_rejects_oversized_raw_product_data(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [{"name": "Golden apple", "raw": {"html": "too much diagnostic data"}}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Product.objects.exists())

    def test_result_stores_raw_observation_and_parser_config_snapshot(self):
        Link.objects.filter(pk=self.source.pk).update(
            parser_config_version="apples-v2",
            parser_map={"item": "//article", "name": ".//h2/text()", "price": ".//span/text()"},
        )
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "worker_name": "spoofed-worker",
                "parser_config_version": "worker-apples-v2",
                "parser_config": {
                    "item": "//article",
                    "name": ".//h2/text()",
                    "price": ".//span/text()",
                },
                "products": [{"name": "Golden apple", "price": "42.50", "raw": {"price": "42,50 грн"}}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(ProductPriceHistory.objects.get().raw_data, {"price": "42,50 грн"})
        attempt = ParserSourceAttempt.objects.get()
        self.assertEqual(attempt.worker_name, "laptop-a")
        self.assertEqual(attempt.parser_config_version, "worker-apples-v2")
        self.assertEqual(attempt.parser_config["item"], "//article")

    @override_settings(PARSER_MISSING_DEACTIVATION_THRESHOLD=2)
    def test_only_complete_snapshots_age_missing_products_and_reappearance_reactivates(self):
        product = Product.objects.create(
            company=self.company,
            category=self.category,
            source_link=self.source,
            source_product_key="golden apple",
            name="Golden apple",
        )

        for complete in (False, True, True):
            lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
            response = self.client.post(
                f"/api/parser/sources/{self.source.id}/results/",
                {
                    "lease_token": lease_response.data["lease_token"],
                    "snapshot_complete": complete,
                    "products": [{"name": "Gala apple"}],
                },
                format="json",
            )
            self.assertEqual(response.status_code, 200)
            Link.objects.filter(pk=self.source.pk).update(last_crawled=None)

        product.refresh_from_db()
        self.assertFalse(product.active)
        self.assertEqual(product.consecutive_missing_count, 2)

        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "products": [{"name": "Golden apple"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertTrue(product.active)
        self.assertEqual(product.consecutive_missing_count, 0)

    def test_empty_complete_snapshot_is_rejected_without_aging_products_or_consuming_lease(self):
        product = Product.objects.create(
            company=self.company,
            category=self.category,
            source_link=self.source,
            source_product_key="golden apple",
            name="Golden apple",
        )
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "snapshot_complete": True,
                "products": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        product.refresh_from_db()
        self.source.refresh_from_db()
        self.assertTrue(product.active)
        self.assertEqual(product.consecutive_missing_count, 0)
        self.assertIsNotNone(self.source.lease_token)
        self.assertFalse(ParserSourceAttempt.objects.exists())

    @override_settings(PARSER_MIN_COMPLETE_SNAPSHOT_RATIO=0.5)
    def test_sharply_reduced_complete_snapshot_is_rejected(self):
        Product.objects.bulk_create(
            [
                Product(
                    company=self.company,
                    category=self.category,
                    source_link=self.source,
                    source_product_key=f"apple-{index}",
                    name=f"Apple {index}",
                )
                for index in range(10)
            ]
        )
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": lease_response.data["lease_token"],
                "snapshot_complete": True,
                "products": [{"name": f"Apple {index}"} for index in range(4)],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("at least 5", str(response.data["snapshot_complete"]))
        self.assertEqual(Product.objects.filter(active=True).count(), 10)
        self.assertFalse(ParserSourceAttempt.objects.exists())

    def test_successful_result_retry_is_idempotent_by_lease_token(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        payload = {
            "lease_token": lease_response.data["lease_token"],
            "products": [{"name": "Golden apple", "price": "42.50"}],
        }

        first_response = self.client.post(f"/api/parser/sources/{self.source.id}/results/", payload, format="json")
        replay_response = self.client.post(f"/api/parser/sources/{self.source.id}/results/", payload, format="json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(replay_response.status_code, 200)
        self.assertTrue(replay_response.data["replayed"])
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(ProductPriceHistory.objects.count(), 1)

    def test_result_submission_rejects_invalid_lease(self):
        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/results/",
            {
                "lease_token": "00000000-0000-0000-0000-000000000000",
                "products": [{"name": "Golden apple", "price": "42.50"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Product.objects.exists())

    def test_failure_submission_records_error_and_releases_lease(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        response = self.client.post(
            f"/api/parser/sources/{self.source.id}/failure/",
            {
                "lease_token": lease_response.data["lease_token"],
                "status": 503,
                "error": "Remote shop timed out",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.source.refresh_from_db()
        self.assertEqual(self.source.last_crawl_status, 503)
        self.assertEqual(self.source.last_error, "Remote shop timed out")
        self.assertIsNone(self.source.last_crawled)
        self.assertIsNone(self.source.lease_token)
        attempt = ParserSourceAttempt.objects.get(source_link=self.source)
        self.assertEqual(attempt.status, ParserSourceAttempt.STATUS_FAILURE)
        self.assertEqual(attempt.worker_name, "laptop-a")
        self.assertEqual(attempt.error, "Remote shop timed out")
        self.assertEqual(attempt.parser_config, {"name": "//h1"})

    def test_failure_submission_retry_is_idempotent_by_lease_token(self):
        lease_response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})
        payload = {
            "lease_token": lease_response.data["lease_token"],
            "status": 503,
            "error": "Remote shop timed out",
        }

        first_response = self.client.post(f"/api/parser/sources/{self.source.id}/failure/", payload, format="json")
        replay_response = self.client.post(f"/api/parser/sources/{self.source.id}/failure/", payload, format="json")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(replay_response.status_code, 200)
        self.assertTrue(replay_response.data["replayed"])
        self.assertEqual(ParserSourceAttempt.objects.filter(status=ParserSourceAttempt.STATUS_FAILURE).count(), 1)
