from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import skipUnlessDBFeature
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITestCase, APITransactionTestCase

from core.registry.models import Variety
from core.utils.tests.factories import PostFactory, StaffUserFactory, UserFactory


def publication_url(variety_id):
    return f"/api/registry/varieties/{variety_id}/publication/"


class VarietyPublicationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.variety = Variety.objects.create(title="Golden Delicious")
        cls.publication = PostFactory()
        cls.staff_token = Token.objects.create(user=StaffUserFactory())

    def setUp(self):
        self.url = publication_url(self.variety.pk)
        self.payload = {"publication_id": self.publication.pk}

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_requires_staff_token(self):
        self.assertEqual(self.client.patch(self.url, self.payload, format="json").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid")
        self.assertEqual(self.client.patch(self.url, self.payload, format="json").status_code, 401)
        self.authenticate(Token.objects.create(user=UserFactory()))
        self.assertEqual(self.client.patch(self.url, self.payload, format="json").status_code, 403)
        self.variety.refresh_from_db()
        self.assertIsNone(self.variety.publication_id)

    def test_saves_link_and_accepts_identical_retry(self):
        self.authenticate(self.staff_token)
        expected = {"variety_id": self.variety.pk, **self.payload}

        for attempt in range(2):
            with self.subTest(attempt=attempt):
                response = self.client.patch(self.url, self.payload, format="json")
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data, expected)
                self.variety.refresh_from_db()
                self.assertEqual(self.variety.publication, self.publication)

    def test_different_publication_preserves_existing_link(self):
        self.authenticate(self.staff_token)
        self.variety.publication = self.publication
        self.variety.save(update_fields=("publication",))

        response = self.client.patch(self.url, {"publication_id": PostFactory().pk}, format="json")

        self.assertEqual(response.status_code, 409, response.data)
        self.assertEqual(response.data["code"], "publication_conflict")
        self.assertEqual(response.data["variety_id"], self.variety.pk)
        self.assertEqual(response.data["publication_id"], self.publication.pk)
        self.variety.refresh_from_db()
        self.assertEqual(self.variety.publication, self.publication)

    def test_unknown_ids_return_not_found(self):
        self.authenticate(self.staff_token)

        missing_variety = self.client.patch(publication_url(self.variety.pk + 1), self.payload, format="json")
        missing_publication = self.client.patch(self.url, {"publication_id": self.publication.pk + 1}, format="json")

        self.assertEqual(missing_variety.status_code, 404)
        self.assertIn("Variety", missing_variety.data["detail"])
        self.assertEqual(missing_publication.status_code, 404)
        self.assertIn("Publication", missing_publication.data["detail"])
        self.variety.refresh_from_db()
        self.assertIsNone(self.variety.publication_id)

    def test_invalid_or_missing_publication_id_preserves_existing_link(self):
        self.authenticate(self.staff_token)
        self.variety.publication = self.publication
        self.variety.save(update_fields=("publication",))

        invalid_ids = (None, 0, -1, True, 1.0, 1.5, str(self.publication.pk), "invalid", [], {})
        for payload in ({}, *({"publication_id": value} for value in invalid_ids)):
            with self.subTest(payload=payload):
                response = self.client.patch(self.url, payload, format="json")
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn("publication_id", response.data)

        self.variety.refresh_from_db()
        self.assertEqual(self.variety.publication, self.publication)


class ConcurrentVarietyPublicationTests(APITransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_requests_for_different_posts_preserve_winner(self):
        variety = Variety.objects.create(title="Golden Delicious")
        url = publication_url(variety.pk)
        posts = PostFactory.create_batch(2)
        token = Token.objects.create(user=StaffUserFactory())
        barrier = Barrier(2)

        def link(publication_id):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
                barrier.wait(timeout=10)
                response = client.patch(url, {"publication_id": publication_id}, format="json")
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = sorted(pool.map(link, (post.pk for post in posts)), key=lambda result: result[0])

        self.assertEqual([status for status, _ in results], [200, 409], results)
        variety.refresh_from_db()
        for _, result in results:
            self.assertEqual(result["publication_id"], variety.publication_id)
