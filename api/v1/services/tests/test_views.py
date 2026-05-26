from core.utils.tests.factories import CategoryFactory, UserFactory
from rest_framework.test import APIClient, APITestCase

api_client = APIClient()


class CategoryReviewsViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = CategoryFactory(slug="view_set_test")

    def test_create_review(self):
        response = self.client.post(
            "/api/category/reviews/", {"description": "description test", "mark": 5, "slug": "view_set_test"}
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(set(response.data), {"pk", "mark", "description"})
        self.assertEqual(response.data["mark"], 5)
        self.assertEqual(response.data["description"], "description test")

    def test_create_review_requires_authentication(self):
        self.client.logout()

        response = self.client.post(
            "/api/category/reviews/",
            {"description": "description test", "mark": 5, "slug": "view_set_test"},
        )

        self.assertEqual(response.status_code, 403)

    def test_create_review_validates_required_fields(self):
        response = self.client.post("/api/category/reviews/", {"slug": "view_set_test"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("mark", response.data)
        self.assertIn("description", response.data)
