import threading
from unittest.mock import patch

from django.db import close_old_connections, transaction
from django.test import TransactionTestCase

from core.adverts.models import Advert
from core.search.indexing import sync_index, write_scope
from core.search.models import SearchDirtyScope
from core.search.query import search_documents


class SearchConcurrencyTests(TransactionTestCase):
    def setUp(self):
        sync_index(rebuild=True)

    def test_older_uncommitted_event_survives_worker_snapshot(self):
        inserted = threading.Event()
        release = threading.Event()
        committed = threading.Event()
        errors = []

        def late_writer():
            close_old_connections()
            try:
                with transaction.atomic():
                    Advert.objects.create(title="Пізнійунікальний", contact="test")
                    inserted.set()
                    if not release.wait(10):
                        raise RuntimeError("Worker did not release writer")
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()
                committed.set()

        thread = threading.Thread(target=late_writer)
        thread.start()
        try:
            self.assertTrue(inserted.wait(10))
            Advert.objects.create(title="Раннійунікальний", contact="test")

            def build_then_commit(generation, kind):
                write_scope(generation, kind)
                release.set()
                self.assertTrue(committed.wait(10))

            with patch("core.search.indexing.write_scope", side_effect=build_then_commit):
                sync_index()
        finally:
            release.set()
            thread.join(10)
        self.assertFalse(errors, errors)
        self.assertFalse(thread.is_alive())
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="advert").exists())
        self.assertFalse(search_documents("Пізнійунікальний").filter(title="Пізнійунікальний").exists())
        sync_index()
        self.assertTrue(search_documents("Пізнійунікальний").filter(title="Пізнійунікальний").exists())

    def test_independent_writers_do_not_lock_the_same_dirty_scope(self):
        release = threading.Event()
        inserted = [threading.Event(), threading.Event()]
        errors = []

        def writer(index):
            close_old_connections()
            try:
                with transaction.atomic():
                    Advert.objects.create(title=f"Паралельний{index}", contact="test")
                    inserted[index].set()
                    if not release.wait(10):
                        raise RuntimeError("Writer release timeout")
            except Exception as exc:
                errors.append(exc)
            finally:
                close_old_connections()

        threads = [threading.Thread(target=writer, args=(index,)) for index in range(2)]
        for thread in threads:
            thread.start()
        try:
            self.assertTrue(all(event.wait(5) for event in inserted), "Source writers blocked each other")
        finally:
            release.set()
            for thread in threads:
                thread.join(10)
        self.assertFalse(errors, errors)
        self.assertEqual(SearchDirtyScope.objects.filter(resource_type="advert").count(), 2)
        sync_index()
        self.assertEqual(
            search_documents("Паралельний0").filter(resource_type="advert", title="Паралельний0").count(), 1
        )
