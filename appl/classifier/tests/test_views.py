from __future__ import unicode_literals

from django.test import TestCase, Client
from django.core.urlresolvers import reverse

from utils.tests.factories import LocationFactory

from rest_framework.test import APIClient, APITestCase

api_client = APIClient()

client = Client()


class LocationAutocompleteTests(TestCase):

    def test_return_query_set(self):
        loc = LocationFactory()
        response = client.get(reverse('location-autocomplete'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['text'], str(loc))
        LocationFactory(value=u'Львів')
        response = client.get(reverse('location-autocomplete'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 2)
        response = client.get(reverse('location-autocomplete') + u'?q=к')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)


class LocationLisiTest(APITestCase):
    def test_response_ok(self):
        LocationFactory()
        response = api_client.get(reverse('location-list'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('pk', response.data['results'][0])
        self.assertIn('value', response.data['results'][0])

    def test_pagination(self):
        LocationFactory.create_batch(11)
        response = api_client.get(reverse('location-list'), data={"page": 2})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 11)
        self.assertEqual(len(response.data['results']), 1)

    def test_filtering(self):
        LocationFactory(value='Київ')
        LocationFactory(value='Краків')
        LocationFactory(value='Хоростків')
        response = api_client.get(reverse('location-list'), data={"loc": "к"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 2)
        response = api_client.get(reverse('location-list'), data={"loc": "кр"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 1)
