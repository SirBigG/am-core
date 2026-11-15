from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.contrib.auth.models import Permission
from django.db import connection, connections, transaction
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITransactionTestCase

from core.companies.models import Company, Link
from core.utils.tests.factories import CategoryFactory, LocationFactory, UserFactory


class ParserCatalogConcurrencyTests(APITransactionTestCase):
    def setUp(self):
        self.company = Company.objects.create(
            name="Concurrent shop",
            website="https://shop.example.com",
            location=LocationFactory(),
            parser_map={"name": "//h1"},
        )
        self.source = Link.objects.create(
            company=self.company,
            category=CategoryFactory(),
            url="https://shop.example.com/products",
        )
        user = UserFactory()
        user.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="companies",
                codename__in=("use_parser_worker_api", "change_company", "add_link"),
            )
        )
        self.token = Token.objects.create(user=user).key
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")

    def background_post(self, path, payload, waiting):
        def observe_company_lock(execute, sql, params, many, context):
            if '"companies_company"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            client = APIClient()
            client.credentials(HTTP_AUTHORIZATION=f"Token {self.token}")
            with connection.execute_wrapper(observe_company_lock):
                return client.post(path, payload, format="json")
        finally:
            connections.close_all()

    def test_company_edit_serializes_with_source_creation_and_leasing(self):
        for action in ("create", "lease"):
            with self.subTest(action=action), ThreadPoolExecutor(max_workers=1) as pool:
                waiting = Event()
                if action == "create":
                    path = "/api/parser/sources/"
                    payload = {
                        "company_id": self.company.pk,
                        "category_id": self.source.category_id,
                        "url": "https://shop.example.com/new",
                    }
                else:
                    path = f"/api/parser/sources/{self.source.pk}/lease/"
                    payload = {}
                with transaction.atomic():
                    Company.objects.select_for_update().get(pk=self.company.pk)
                    future = pool.submit(self.background_post, path, payload, waiting)
                    self.assertTrue(waiting.wait(timeout=5), "API did not acquire the company lock")
                    self.assertFalse(future.done(), "Concurrent write bypassed the company lock")
                    response = self.client.patch(
                        f"/api/parser/companies/{self.company.pk}/",
                        {"parser_map": {"name": f"//{action}"}},
                        format="json",
                    )
                    self.assertEqual(response.status_code, 200, response.data)
                response = future.result(timeout=5)
                self.assertEqual(response.status_code, 201 if action == "create" else 200, response.data)
                if action == "create":
                    self.assertEqual(response.data["parser_map"], {"name": "//create"})
                else:
                    conflict = self.client.patch(
                        f"/api/parser/companies/{self.company.pk}/",
                        {"parser_map": {"name": "//new"}},
                        format="json",
                    )
                    self.assertEqual(conflict.status_code, 409, conflict.data)
