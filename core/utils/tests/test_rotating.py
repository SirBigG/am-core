from django.core.cache import cache
from django.test import TestCase

from core.adverts.models import Advert
from core.utils.rotating import get_rotating_ids


class RotatingIdsTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_cache_key_changes_when_rows_are_replaced(self):
        first = Advert.objects.create(title="first", description="test", price=100, contact="test")

        self.assertEqual(get_rotating_ids(Advert.objects.all(), "test", 4), [first.pk])

        first.delete()
        replacement = Advert.objects.create(title="replacement", description="test", price=100, contact="test")

        self.assertEqual(get_rotating_ids(Advert.objects.all(), "test", 4), [replacement.pk])
