from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.classifier.models import Category
from core.utils.tests.factories import CategoryFactory, LocationFactory

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
            value="Рослинництво",
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
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["id"], str(self.basil.pk))
        self.assertEqual(response.json()["results"][0]["text"], str(self.basil))
        self.assertIn("selected_text", response.json()["results"][0])

    def test_search_diary_species_children(self):
        response = client.get(reverse("diary-plant-category-autocomplete") + "?q=баз")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 1)
        self.assertEqual(response.json()["results"][0]["id"], str(self.basil.pk))
        self.assertEqual(response.json()["results"][0]["text"], str(self.basil))
        self.assertIn("selected_text", response.json()["results"][0])


class CategoriesIndexTests(TestCase):
    def test_category_tree_is_loaded_without_per_node_queries(self):
        for root_index in range(3):
            root = CategoryFactory(value=f"Root {root_index}")
            for child_index in range(3):
                child = CategoryFactory(parent=root, value=f"Child {root_index}-{child_index}")
                CategoryFactory(parent=child, value=f"Leaf {root_index}-{child_index}")
        cache.clear()

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("categories"))

        category_queries = [query["sql"] for query in queries if 'FROM "classifier_category"' in query["sql"]]
        self.assertEqual(response.status_code, 200)
        self.assertLessEqual(len(category_queries), 2)
