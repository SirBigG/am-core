# -*- coding: utf-8 -*-

from django.test import TestCase, Client
from django.core.urlresolvers import reverse

from utils.tests.factories import LocationFactory

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
