from django.test import Client, TestCase
from django.urls import reverse

from core.classifier.models import Category
from core.utils.tests.factories import LocationFactory

client = Client()


class LocationAutocompleteTests(TestCase):

    def test_return_query_set(self):
        loc = LocationFactory()
        response = client.get(reverse("location-autocomplete"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["text"], str(loc))
        LocationFactory(value="Львів")
        response = client.get(reverse("location-autocomplete"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 2)
        # Case sensitive because used Sqlite backend for tests
        response = client.get(reverse("location-autocomplete") + "?q=К")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)


class DiaryPlantCategoryAutocompleteTests(TestCase):
    def setUp(self):
        self.parent = Category.objects.create(
            slug="plants",
            value="Рослини",
            is_diary_species_parent=True,
        )
        self.basil = Category.objects.create(slug="basil", value="Базилік", parent=self.parent)
        Category.objects.create(slug="cabbage", value="Капуста")
        Category.objects.create(
            slug="inactive-basil",
            value="Неактивний базилік",
            parent=self.parent,
            is_active=False,
        )

    def test_return_diary_species_children(self):
        response = client.get(reverse("diary-plant-category-autocomplete"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [{"id": str(self.basil.pk), "text": str(self.basil)}])

    def test_search_diary_species_children(self):
        response = client.get(reverse("diary-plant-category-autocomplete") + "?q=баз")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [{"id": str(self.basil.pk), "text": str(self.basil)}])
