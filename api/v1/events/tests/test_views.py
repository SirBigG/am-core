from datetime import datetime, timedelta

from core.events.models import Event
from core.utils.tests.factories import EventFactory, EventTypeFactory, LocationFactory, UserFactory
from core.utils.tests.utils import make_image
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase


class EventTypeListTests(APITestCase):
    test_url = reverse("event-types-list")

    def test_empty_list(self):
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 0)

    def test_with_data(self):
        event_type = EventTypeFactory()
        response = self.client.get(self.test_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0], {"pk": event_type.pk, "title": event_type.title})


class EventCreateTest(APITestCase):
    test_url = reverse("event-create")

    def test_not_authorized(self):
        response = self.client.post(self.test_url)
        self.assertEqual(response.status_code, 403)

    def test_create_success(self):
        location = LocationFactory()
        type_ = EventTypeFactory()
        user = UserFactory()
        self.client.force_login(user)
        response = self.client.post(
            self.test_url,
            data={
                "title": "title",
                "text": "text",
                "type": type_.pk,
                "location": location.pk,
                "poster": make_image(),
                "address": "address",
                "start": datetime.now(),
                "stop": datetime.now(),
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            set(response.data), {"title", "address", "text", "start", "stop", "type", "location", "poster", "url"}
        )
        self.assertEqual(response.data["url"], Event.objects.get(user=user).get_absolute_url())
        self.assertEqual(Event.objects.filter(user=user).count(), 1)

    def test_create_validation_errors(self):
        user = UserFactory()
        self.client.force_login(user)

        response = self.client.post(self.test_url, data={})

        self.assertEqual(response.status_code, 400)
        self.assertIn("title", response.data)
        self.assertIn("location", response.data)


class EventListTests(APITestCase):
    test_url = reverse("event-list")

    def test_returns_only_active_future_events(self):
        active = EventFactory(
            status=1, start=timezone.now() + timedelta(days=1), stop=timezone.now() + timedelta(days=2)
        )
        EventFactory(status=0, start=timezone.now() + timedelta(days=1), stop=timezone.now() + timedelta(days=2))
        EventFactory(status=1, start=timezone.now() - timedelta(days=2), stop=timezone.now() - timedelta(days=1))

        response = self.client.get(self.test_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], active.title)
        self.assertEqual(response.data[0]["url"], active.get_absolute_url())
