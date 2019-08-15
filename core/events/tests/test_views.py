from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.utils.tests.factories import EventFactory


class DetailEventView(TestCase):
    def test_response(self):
        event = EventFactory()
        response = self.client.get(reverse('events:event-detail', args=(event.slug,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/detail.html')


class EventListViewTests(TestCase):
    def test_response(self):
        events = [EventFactory(status=1, start=timezone.now()),
                  EventFactory(status=1, start=timezone.now() + timezone.timedelta(days=1)),
                  EventFactory(status=1, start=timezone.now() + timezone.timedelta(days=2))
                  ]
        EventFactory(status=1, start=timezone.now() - timezone.timedelta(days=2))
        response = self.client.get(reverse('events:event-list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/list.html')
        for event, test in zip(response.context["object_list"], events):
            self.assertEqual(event.pk, test.pk)
