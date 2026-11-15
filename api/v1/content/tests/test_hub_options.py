from django.core.cache import cache
from django.db import connection
from rest_framework.authtoken.models import Token
from rest_framework.test import APITransactionTestCase

from core.classifier.models import CategoryHub, CategoryHubSection
from core.posts.models import GuideSection, GuideSectionArticle
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class HubOptionsTests(APITransactionTestCase):
    def test_detail_metadata_does_not_lock_rows_outside_a_write_transaction(self):
        cache.clear()
        self.addCleanup(cache.clear)
        user = StaffUserFactory(is_superuser=True)
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        root = CategoryFactory()
        category = CategoryFactory(parent=root)
        target = CategoryFactory(parent=root)
        hub = CategoryHub.objects.create(category=category)
        section = CategoryHubSection.objects.create(hub=hub, category=target, role="varieties")
        guide = GuideSection.objects.create(category=category, title="Step")
        placement = GuideSectionArticle.objects.create(section=guide, post=PostFactory(rubric=target))
        queries = []

        def capture(execute, sql, params, many, context):
            queries.append(sql)
            return execute(sql, params, many, context)

        for resource, pk in (
            ("hubs", hub.pk),
            ("hub-sections", section.pk),
            ("guide-sections", guide.pk),
            ("guide-placements", placement.pk),
        ):
            with self.subTest(resource=resource), connection.execute_wrapper(capture):
                response = self.client.options(f"/api/content/{resource}/{pk}/")
                self.assertEqual(response.status_code, 200, response.data)
                self.assertIn("PUT", response.data["actions"])
                self.assertIn("no-store", response["Cache-Control"])
        self.assertFalse(any("FOR UPDATE" in sql for sql in queries))
        queries.clear()
        with connection.execute_wrapper(capture):
            response = self.client.patch(f"/api/content/hubs/{hub.pk}/", {"layout": "sectioned"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(any("FOR UPDATE" in sql for sql in queries))
