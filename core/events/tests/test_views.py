from django.test import TestCase
from django.urls import reverse

from core.utils.tests.factories import EventFactory


class DetailEventView(TestCase):
    def test_response(self):
        event = EventFactory()
        response = self.client.get(reverse('events:event-detail', args=(event.slug,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'events/detail.html')
