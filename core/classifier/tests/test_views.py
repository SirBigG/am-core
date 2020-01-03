from django.test import TestCase, Client
from django.urls import reverse

from core.utils.tests.factories import LocationFactory

client = Client()


class LocationAutocompleteTests(TestCase):

    def test_return_query_set(self):
        loc = LocationFactory()
        response = client.get(reverse('location-autocomplete'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['results'][0]['text'], str(loc))
        LocationFactory(value='Львів')
        response = client.get(reverse('location-autocomplete'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 2)
        # Case sensitive because used SqlLite backend for tests
        response = client.get(reverse('location-autocomplete') + '?q=К')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['results']), 1)
