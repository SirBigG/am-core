from __future__ import unicode_literals

from django.test import TestCase

from utils.tests.factories import LocationFactory, CountryFactory, \
    RegionFactory, AreaFactory, CategoryFactory

from appl.classifier.models import Location


class LocationModelTests(TestCase):

    def setUp(self):
        self.location = LocationFactory()

    def test_creation(self):
        self.assertEqual(Location.objects.count(), 1)

    def test_str_representation(self):
        self.assertEqual(str(self.location),
                         '%s (%s %s)' % (self.location.value, str(self.location.region), str(self.location.area)))

    def test_fields_exists(self):
        self.assertTrue(hasattr(self.location, 'slug'))
        self.assertTrue(hasattr(self.location, 'value'))
        self.assertTrue(hasattr(self.location, 'country'))
        self.assertTrue(hasattr(self.location, 'region'))
        self.assertTrue(hasattr(self.location, 'area'))


class CountryTests(TestCase):

    def setUp(self):
        self.country = CountryFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.country), self.country.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.country, 'slug'))
        self.assertTrue(hasattr(self.country, 'short_slug'))
        self.assertTrue(hasattr(self.country, 'value'))


class RegionTests(TestCase):

    def setUp(self):
        self.region = RegionFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.region), self.region.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.region, 'slug'))
        self.assertTrue(hasattr(self.region, 'value'))


class AreaTests(TestCase):

    def setUp(self):
        self.area = AreaFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.area), self.area.value)

    def test_fields_exist(self):
        self.assertTrue(hasattr(self.area, 'slug'))
        self.assertTrue(hasattr(self.area, 'value'))


class CategoryTests(TestCase):

    def setUp(self):
        self.category = CategoryFactory()

    def test_str_representation(self):
        self.assertEqual(str(self.category), u'Категорія')

    def test_default_is_for_user(self):
        self.assertFalse(self.category.is_for_user)
