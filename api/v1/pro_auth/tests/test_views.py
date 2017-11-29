from __future__ import unicode_literals


from core.utils.tests.factories import UserFactory

from rest_framework.test import APIClient, APITestCase

api_client = APIClient()


class UserViewSetTests(APITestCase):
    def setUp(self):
        self.user = UserFactory()
        self.user.set_password('12345')
        self.user.save()
        api_client.login(email=self.user.email, password='12345')

    def test_put_response_ok(self):
        response = api_client.put('/api/users/', data={'phone1': self.user.phone1,
                                                       'email': self.user.email,
                                                       'location': self.user.location.pk})
        self.assertEqual(response.status_code, 200)

    def test_response_with_error(self):
        response = api_client.put('/api/users/', data={'phone1': self.user.phone1,
                                                       'email': '',
                                                       'location': self.user.location.pk})

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)
        self.assertNotIn('phone1', response.data)

    def test_response_ok(self):
        response = api_client.get('/api/users/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.data)
        self.assertEqual(response.data['email'], self.user.email)
        self.assertEqual(response.data['location'], {'pk': self.user.location.pk,
                                                     'value': str(self.user.location)})

    def test_personal_permission(self):
        api_client.logout()
        # Test get
        response = api_client.get('/api/users/')
        self.assertEqual(response.status_code, 403)
        # Test put
        response = api_client.put('/api/users/', data={'phone1': '+38099123467',
                                                       'email': 'test@test.com',
                                                       'location': self.user.location.pk})

        self.assertEqual(response.status_code, 403)
