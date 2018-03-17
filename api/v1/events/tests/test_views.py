from datetime import datetime

from django.urls import reverse

from rest_framework.test import APITestCase

from core.utils.tests.factories import EventTypeFactory, UserFactory, LocationFactory
from core.utils.tests.utils import make_image

from core.events.models import Event


class EventTypeListTests(APITestCase):
    test_url = reverse('event-types-list')

    def test_empty_list(self):
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_with_data(self):
        EventTypeFactory()
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)


class EventCreateTest(APITestCase):
    test_url = reverse('event-create')

    def test_not_authorized(self):
        response = self.client.post(self.test_url)
        self.assertEqual(response.status_code, 403)

    def test_create_success(self):
        location = LocationFactory()
        type_ = EventTypeFactory()
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(self.test_url, data={'title': 'title', 'text': 'text', 'type': type_.pk,
                                                         'location': location.pk, 'poster': make_image(),
                                                         'address': 'address', 'start': datetime.now(),
                                                         'stop': datetime.now()})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Event.objects.filter(user=user).count(), 1)
