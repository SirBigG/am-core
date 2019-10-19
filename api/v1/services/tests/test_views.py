from core.utils.tests.factories import UserFactory, CategoryFactory

from rest_framework.test import APIClient, APITestCase

api_client = APIClient()


class CategoryReviewsViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.client.force_login(self.user)
        self.category = CategoryFactory(slug='view_set_test')

    def test_create_review(self):
        response = self.client.post('/api/category/reviews/', {'description': 'description test',
                                                               'mark': 5, 'slug': 'view_set_test'})
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data)
