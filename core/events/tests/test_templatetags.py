from django.test import TestCase
from django.core.cache import cache
from django.utils import timezone

from core.events.templatetags.events_extras import events_list

from core.utils.tests.factories import EventFactory


class EventTemplatetagsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_not_events(self):
        self.assertEqual(len(events_list()['events']), 0)

    def test_with_events(self):
        EventFactory.create_batch(2, status=1)
        self.assertEqual(len(events_list()['events']), 2)

    def test_not_active_events(self):
        EventFactory.create_batch(2, status=0)
        self.assertEqual(len(events_list()['events']), 0)

    def test_today_start_filter(self):
        EventFactory.create_batch(2, status=1, start=timezone.now() - timezone.timedelta(hours=2))
        self.assertEqual(len(events_list()['events']), 2)
        # Test filter for past events
        EventFactory.create_batch(2, status=1, start=timezone.now() - timezone.timedelta(days=2))
        self.assertEqual(len(events_list()['events']), 2)
