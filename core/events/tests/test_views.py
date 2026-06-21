from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.events.forms import EventAddForm
from core.utils.tests.factories import EventFactory, EventTypeFactory, LocationFactory


class DetailEventView(TestCase):
    def test_response(self):
        event = EventFactory()
        response = self.client.get(reverse("events:event-detail", args=(event.slug,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/detail.html")
        self.assertContains(response, "site-detail-panel")

    def test_events_are_active_by_default(self):
        event = EventFactory()

        self.assertTrue(event.status)


class EventListViewTests(TestCase):
    def test_response(self):
        EventFactory(status=1, start=timezone.now())
        EventFactory(status=1, start=timezone.now() + timezone.timedelta(days=1))
        EventFactory(status=1, start=timezone.now() + timezone.timedelta(days=2))
        EventFactory(status=1, start=timezone.now() - timezone.timedelta(days=2))
        response = self.client.get(reverse("events:event-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/list.html")
        # for event, test in zip(response.context["object_list"], events):
        #     self.assertEqual(event.pk, test.pk)


class EventFormViewTests(TestCase):
    def test_create_form_renders(self):
        EventTypeFactory()
        LocationFactory()

        response = self.client.get(reverse("events:event-form"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "events/form.html")
        self.assertIsInstance(response.context["form"], EventAddForm)
        self.assertContains(response, "site-login-prompt")
        self.assertContains(response, "/login/?next=/events/create/")
