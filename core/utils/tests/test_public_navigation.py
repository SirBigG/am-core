from django.core.cache import cache
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import resolve, reverse

from core.utils.context_processors import ROOT_CATEGORY_LINKS_CACHE_KEY, public_navigation
from core.utils.tests.factories import CategoryFactory


class PublicNavigationTests(TestCase):
    def setUp(self):
        cache.delete(ROOT_CATEGORY_LINKS_CACHE_KEY)
        self.addCleanup(cache.delete, ROOT_CATEGORY_LINKS_CACHE_KEY)
        self.request = RequestFactory().get("/")

    def test_two_levels_use_one_query_and_preserve_category_urls(self):
        root = CategoryFactory(value="Рослинництво", slug="plants")
        CategoryFactory(parent=root, value="Зернові", slug="grains")
        CategoryFactory(parent=root, value="Бобові", slug="legumes")
        CategoryFactory(parent=root, is_active=False, slug="hidden-child")
        CategoryFactory(parent=root.children.get(slug="grains"), slug="deeper")
        hidden_root = CategoryFactory(is_active=False, slug="hidden-root")
        CategoryFactory(parent=hidden_root, slug="orphan")
        CategoryFactory(value="Інше", slug="other")

        with self.assertNumQueries(1):
            links = public_navigation(self.request)["root_category_links"]
        self.assertEqual(
            links,
            [
                {"title": "Інше", "url": "/categories/other/", "children": []},
                {
                    "title": "Рослинництво",
                    "url": "/categories/plants/",
                    "children": [
                        {"title": "Бобові", "url": "/legumes/"},
                        {"title": "Зернові", "url": "/grains/"},
                    ],
                },
            ],
        )
        with self.assertNumQueries(0):
            self.assertEqual(public_navigation(self.request)["root_category_links"], links)

    def test_old_flat_cache_does_not_hide_subcategories(self):
        cache.set("public_root_category_links_v1", [{"title": "Stale", "url": "/stale/"}])
        self.addCleanup(cache.delete, "public_root_category_links_v1")
        root = CategoryFactory(slug="plants")
        CategoryFactory(parent=root, slug="grains")
        self.assertEqual(len(public_navigation(self.request)["root_category_links"][0]["children"]), 1)

    def test_shared_menus_render_disclosures_without_registry_links(self):
        root = CategoryFactory(value="Рослинництво", slug="plants")
        CategoryFactory(parent=root, value="Зернові", slug="grains")
        CategoryFactory(value="Інше", slug="other")
        context = public_navigation(self.request)
        context["request"] = self.request
        for template in ("header.html", "footer.html"):
            with self.subTest(template=template):
                html = render_to_string(template, context)
                self.assertIn('<details class="category-navigation">', html)
                self.assertIn('href="/grains/"', html)
                self.assertIn('href="/categories/plants/"', html)
                self.assertIn('href="/categories/other/"', html)
                self.assertIn('data-bs-auto-close="outside"', html)
                self.assertNotIn("/registry/", html)

    def test_registry_route_is_preserved(self):
        self.assertEqual(reverse("registry:index"), "/registry/")
        self.assertEqual(resolve("/registry/").view_name, "registry:index")
