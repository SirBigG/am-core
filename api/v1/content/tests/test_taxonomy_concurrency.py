from concurrent.futures import ThreadPoolExecutor
from threading import Event

from django.db import connection, connections, transaction
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient, APITransactionTestCase

from api.v1.content.taxonomy import lock_taxonomy
from core.classifier.models import Category
from core.utils.tests.factories import CategoryFactory, StaffUserFactory


class TaxonomyConcurrencyTests(APITransactionTestCase):
    def test_overlapping_moves_revalidate_tree_after_waiting_for_the_lock(self):
        root = CategoryFactory()
        first = CategoryFactory(parent=root)
        second = CategoryFactory(parent=root)
        token = Token.objects.create(user=StaffUserFactory(is_superuser=True)).key
        waiting = Event()

        def background_move():
            def observe(execute, sql, params, many, context):
                if sql.startswith("LOCK TABLE classifier_category"):
                    waiting.set()
                return execute(sql, params, many, context)

            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
                with connection.execute_wrapper(observe):
                    return client.patch(f"/api/content/categories/{second.pk}/", {"parent": first.pk}, format="json")
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic():
                lock_taxonomy()
                future = pool.submit(background_move)
                self.assertTrue(waiting.wait(timeout=5))
                self.assertFalse(future.done())
                self.client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
                response = self.client.patch(
                    f"/api/content/categories/{first.pk}/", {"parent": second.pk}, format="json"
                )
                self.assertEqual(response.status_code, 200, response.data)
            response = future.result(timeout=5)
        self.assertEqual(response.status_code, 400, response.data)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(first.parent_id, second.pk)
        self.assertEqual(second.parent_id, root.pk)
        self.assertEqual(
            list(
                Category.objects.filter(pk__in=[root.pk, first.pk, second.pk])
                .order_by("lft")
                .values_list("pk", flat=True)
            ),
            [root.pk, second.pk, first.pk],
        )
