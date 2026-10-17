from django.test import TestCase

from core.classifier.models import CategoryPresentationMode, Location
from core.utils.tests.factories import AreaFactory, CategoryFactory, CountryFactory, LocationFactory, RegionFactory


class LocationModelTests(TestCase):

    def setUp(self):
        self.location = LocationFactory()

    def test_creation(self):
        self.assertEqual(Location.objects.count(), 1)

    def test_str_representation(self):
        self.assertEqual(
            str(self.location),
            f"{self.location.value} ({str(self.location.region)} {str(self.location.area)})",
        )

    def test_fields_exists(self):
        self.assertTrue(hasattr(self.location, "slug"))
        self.assertTrue(hasattr(self.location, "value"))
        self.assertTrue(hasattr(self.location, "country"))
        self.assertTrue(hasattr(self.location, "region"))
        self.assertTrue(hasattr(self.location, "area"))


class CountryTests(TestCase):

    def setUp(self):
        self.country = CountryFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.country), self.country.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.country, "slug"))
        self.assertTrue(hasattr(self.country, "short_slug"))
        self.assertTrue(hasattr(self.country, "value"))


class RegionTests(TestCase):

    def setUp(self):
        self.region = RegionFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.region), self.region.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.region, "slug"))
        self.assertTrue(hasattr(self.region, "value"))


class AreaTests(TestCase):

    def setUp(self):
        self.area = AreaFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.area), self.area.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.area, "slug"))
        self.assertTrue(hasattr(self.area, "value"))


class CategoryTests(TestCase):

    def setUp(self):
        self.category = CategoryFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.category), "Категорія")

    def test_default_is_for_user(self):
        self.assertFalse(self.category.is_for_user)

    def test_default_presentation_is_catalog(self):
        self.category.refresh_from_db()
        self.assertEqual(self.category.presentation_mode, CategoryPresentationMode.CATALOG)

    def test_guide_presentation_preserves_category_url_and_identity(self):
        self.category.parent = CategoryFactory(parent=CategoryFactory())
        self.category.save()
        self.category.refresh_from_db()
        original_url = self.category.absolute_url
        original_slug = self.category.slug
        self.category.presentation_mode = CategoryPresentationMode.GUIDE_HUB
        self.category.save()
        self.category.refresh_from_db()
        self.assertEqual(self.category.presentation_mode, "guide_hub")
        self.assertEqual(self.category.absolute_url, original_url)
        self.assertEqual(self.category.slug, original_slug)

    def test_get_absolute_url(self):
        root = CategoryFactory(slug="root")
        first = CategoryFactory(slug="first", parent=root)
        second = CategoryFactory(slug="second", parent=first)
        self.assertEqual(first.get_absolute_url(), "/first/")
        self.assertEqual(second.get_absolute_url(), "/first/second/")
