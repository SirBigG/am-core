from datetime import timedelta

from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core.classifier.models import Category
from core.posts.models import Post, SearchStatistic
from core.search.indexing import sync_index
from core.search.query import search_documents
from core.utils.tests.factories import CategoryFactory, UserFactory


@override_settings(UNIFIED_SEARCH_ENABLED=True)
class SearchReleaseRegressions(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.parent = CategoryFactory(parent=CategoryFactory())
        cls.category = CategoryFactory(parent=cls.parent)
        cls.user = UserFactory()
        cls.token = Token.objects.create(user=cls.user)

    def create_api_post(self):
        response = self.client.post(
            "/api/content/posts/",
            {"title": "Регресійнийматеріал", "text": "Регресійнийматеріал", "rubric": self.category.pk, "status": True},
            content_type="application/json",
            headers={"authorization": f"Token {self.token.key}"},
        )
        self.assertEqual(response.status_code, 201)
        return response, Post.objects.get(pk=response.data["id"])

    def test_api_create_returns_persisted_canonical_url_and_public_detail(self):
        response, post = self.create_api_post()
        expected = reverse("post-detail", args=[self.parent.slug, self.category.slug, post.slug, post.pk])
        self.assertEqual(post.absolute_url, expected)
        self.assertEqual(response.data["url"], expected)
        self.assertEqual(post.publisher_id, self.user.pk)
        self.assertEqual(self.client.get(expected).status_code, 200)

    def test_api_post_is_searchable_after_queue_refresh_and_rebuild_without_get_repairs(self):
        sync_index(rebuild=True)
        _, post = self.create_api_post()
        for rebuild in (False, True):
            with self.subTest(rebuild=rebuild):
                sync_index(rebuild=rebuild)
                matches = search_documents(post.title).filter(resource_type="post", source_id=post.pk)
                self.assertTrue(matches.exists())
                self.assertEqual(matches.get().canonical_url, post.absolute_url)
        # Neither response rendering mode may repair source URLs as a side effect.
        for enabled in (True, False):
            with self.subTest(enabled=enabled), override_settings(UNIFIED_SEARCH_ENABLED=enabled):
                with CaptureQueriesContext(connection) as queries:
                    response = self.client.get("/search/", {"q": post.title})
                self.assertEqual(response.context["paginator"].count, 1)
                self.assertContains(response, post.absolute_url)
                writes = [
                    row["sql"] for row in queries if row["sql"].startswith(('UPDATE "post"', 'INSERT INTO "post"'))
                ]
                self.assertEqual(writes, [])

    def test_both_modes_hide_future_inactive_and_hidden_ancestor_posts(self):
        _, post = self.create_api_post()
        sync_index(rebuild=True)
        past = timezone.now() - timedelta(days=1)
        for changes, hidden_parent in (
            ({"status": True, "publish_date": timezone.now() + timedelta(days=2)}, False),
            ({"status": True, "publish_date": past}, True),
            ({"status": False, "publish_date": past}, False),
        ):
            Post.objects.filter(pk=post.pk).update(**changes)
            Category.objects.filter(pk=self.parent.pk).update(is_active=not hidden_parent)
            for enabled in (True, False):
                with self.subTest(enabled=enabled, changes=changes, hidden_parent=hidden_parent):
                    with override_settings(UNIFIED_SEARCH_ENABLED=enabled):
                        response = self.client.get("/search/", {"q": post.title})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.context["paginator"].count, 0)
                    self.assertNotContains(response, post.absolute_url)
                    self.assertIn("no-store", response.headers["Cache-Control"])
                    self.assertContains(response, '<meta name="robots" content="noindex,follow">', html=True)

    @override_settings(UNIFIED_SEARCH_ENABLED=False)
    def test_fallback_works_without_reading_search_index_state_or_documents(self):
        _, post = self.create_api_post()
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get("/search/", {"q": post.title})
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertFalse(any('"search_search' in row["sql"] for row in queries))
        self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(UNIFIED_SEARCH_ENABLED=False)
    def test_fallback_bounds_input_and_does_not_duplicate_navigation_statistics(self):
        response = self.client.get("/search/", {"q": "  " + "x" * 1000 + "  "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["search_query"], "x" * 255)
        self.assertContains(response, 'maxlength="255"')
        self.assertEqual(SearchStatistic.objects.get().search_phrase, "x" * 255)
        self.client.get("/search/", {"q": "x" * 1000, "page": 1})
        self.assertEqual(SearchStatistic.objects.count(), 1)
        self.assertIn("no-store", response.headers["Cache-Control"])

    @override_settings(UNIFIED_SEARCH_ENABLED=False)
    def test_fallback_whitespace_query_returns_form_without_empty_state_or_statistic(self):
        response = self.client.get("/search/", {"q": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 0)
        self.assertFalse(SearchStatistic.objects.exists())
        self.assertNotContains(response, "Нічого не знайшли")
