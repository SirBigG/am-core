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

    def test_lease_rejects_source_crawled_less_than_one_day_ago(self):
        Link.objects.filter(pk=self.source.pk).update(
            last_crawled=timezone.now() - timedelta(hours=23, minutes=59),
            crawl_interval_minutes=30,
        )

        response = self.client.post(f"/api/parser/sources/{self.source.id}/lease/", {"duration_minutes": 15})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["detail"], "Source is not due for crawling.")
        self.source.refresh_from_db()
        self.assertIsNone(self.source.lease_token)

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
