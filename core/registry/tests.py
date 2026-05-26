from django.test import TestCase
from django.urls import reverse

from core.registry.models import Variety, VarietyCategory
from core.utils.tests.factories import CountryFactory


class RegistryPublicViewTests(TestCase):
    def setUp(self):
        self.root = VarietyCategory.objects.create(title="Зернові", slug="grain")
        self.child = VarietyCategory.objects.create(title="Пшениця", slug="wheat", parent=self.root)

    def test_registry_index_renders_root_categories(self):
        response = self.client.get(reverse("registry:index"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registry/index.html")
        self.assertIn(self.root, response.context["object_list"])

    def test_registry_category_renders_child_categories(self):
        response = self.client.get(reverse("registry:index-parent", kwargs={"root_slug": self.root.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registry/categories.html")
        self.assertEqual(response.context["category"], self.root)
        self.assertIn(self.child, response.context["object_list"])

    def test_registry_variety_list_renders_child_varieties(self):
        country = CountryFactory(short_slug="ua")
        Variety.objects.create(title="Сорт А", slug="sort-a", category=self.child, original_country=country)

        response = self.client.get(
            reverse("registry:index-parent", kwargs={"root_slug": self.root.slug, "child_slug": self.child.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registry/varieties.html")
        self.assertEqual(response.context["category"], self.child)
        self.assertEqual(response.context["posts"][0][0], "С")

    def test_registry_variety_list_returns_404_for_unknown_child(self):
        response = self.client.get(
            reverse("registry:index-parent", kwargs={"root_slug": self.root.slug, "child_slug": "missing"})
        )

        self.assertEqual(response.status_code, 404)
