from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from queue import Queue
from time import monotonic, sleep

from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection, transaction
from django.http import Http404
from django.test import TestCase, TransactionTestCase

from core.catalog.access_models import PrivateRelationSite, RelationEntityGrant, RelationSiteGrant
from core.catalog.models import CatalogEntity
from core.catalog.relation_access import RelationAccess
from core.catalog.relation_service import RelationConflict
from core.catalog.relations import RelationAuditEvent, RelationRecord, ReviewState
from core.utils.tests.factories import PostFactory, StaffUserFactory, UserFactory


class RelationAccessTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="a.example.test", name="A")
        self.other = Site.objects.create(domain="b.example.test", name="B")
        self.actor = self.editor()
        self.grant = RelationSiteGrant.objects.create(actor=self.actor, site=self.site, can_edit=True)
        self.entities = [
            CatalogEntity.objects.create(kind="crop", provenance={"source": "fixture"}, created_by=self.actor)
            for _ in range(3)
        ]
        for entity in self.entities[:2]:
            RelationEntityGrant.objects.create(grant=self.grant, entity=entity)
        self.access = RelationAccess(self.actor, self.site.pk)

    def editor(self):
        actor = StaffUserFactory()
        actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=["view_relationrecord", "add_relationrecord", "change_relationrecord"],
            )
        )
        return actor

    def draft(self, access=None, participants=None, **kwargs):
        access = self.access if access is None else access
        participants = self.entities[:2] if participants is None else participants
        return access.save_draft(
            type_code="related_to",
            schema_version=1,
            participants={"member": [p.pk for p in participants]},
            **kwargs,
        )

    def test_site_grant_and_model_permissions_are_separate(self):
        with self.assertRaises(PermissionDenied):
            RelationAccess(self.actor, self.other.pk).records()
        with self.assertRaises(PermissionDenied):
            RelationAccess(self.actor, None).participants()
        for actor in (StaffUserFactory(is_superuser=True), UserFactory(), StaffUserFactory()):
            if not actor.is_superuser:
                RelationSiteGrant.objects.create(actor=actor, site=self.other)
            with self.subTest(actor=actor.pk), self.assertRaises(PermissionDenied):
                RelationAccess(actor, self.other.pk).records()
        self.grant.can_edit = False
        self.grant.save(update_fields=["can_edit"])
        self.assertEqual(self.access.participants().count(), 2)
        with self.assertRaises(PermissionDenied):
            self.draft()

    def test_record_history_and_direct_ids_are_bound_to_site_actor_access(self):
        revision = self.draft()
        self.assertEqual(PrivateRelationSite.objects.get(pk=revision.record_id).site_id, self.site.pk)
        other = self.editor()
        foreign = RelationSiteGrant.objects.create(actor=other, site=self.other, can_edit=True)
        for entity in self.entities[:2]:
            RelationEntityGrant.objects.create(grant=foreign, entity=entity)
        other_access = RelationAccess(other, self.other.pk)
        self.assertFalse(other_access.records().exists())
        version = RelationRecord.objects.get(pk=revision.record_id).lock_version
        with self.assertRaises(Http404):
            self.draft(other_access, record_id=revision.record_id, expected_version=version)
        with self.assertRaises(Http404):
            other_access.submit(record_id=revision.record_id, revision_id=revision.pk, expected_version=version)
        with self.assertRaises(ValidationError):
            self.draft(other_access)
        self.assertEqual(RelationRecord.objects.count(), 1)

    def test_current_participant_grants_gate_search_and_each_write(self):
        self.assertCountEqual(
            self.access.participants().values_list("entity_id", flat=True), [p.pk for p in self.entities[:2]]
        )
        with self.assertRaises(ValidationError):
            self.draft(participants=self.entities[1:])
        revision = self.draft()
        version = RelationRecord.objects.get(pk=revision.record_id).lock_version
        with self.assertRaises(RelationConflict):
            self.draft(record_id=revision.record_id, expected_version=version - 1)
        result = self.access.submit(record_id=revision.record_id, revision_id=revision.pk, expected_version=version)
        self.assertEqual(result.state, ReviewState.SUBMITTED)
        self.assertEqual(RelationAuditEvent.objects.get(action="submit").actor, self.actor)
        RelationEntityGrant.objects.filter(grant=self.grant, entity=self.entities[0]).delete()
        self.assertFalse(self.access.records().exists())
        with self.assertRaises(Http404):
            self.access.archive_private(record_id=revision.record_id, expected_version=version + 1)
        self.assertFalse(RelationRecord.objects.get(pk=revision.record_id).archived)

    def test_mismatched_label_anchor_fails_closed(self):
        post = PostFactory(entity=self.entities[2])
        RelationEntityGrant.objects.filter(grant=self.grant, entity=self.entities[0]).update(post=post)
        self.assertFalse(self.access.participants().filter(entity=self.entities[0]).exists())
        with self.assertRaises(ValidationError):
            self.draft()


class RelationAnchorRaceTests(TransactionTestCase):
    def test_anchor_change_first_denies_draft_after_wait(self):
        self._exercise_anchor_race(anchor_first=True)

    def test_draft_first_keeps_anchor_stable_until_commit(self):
        self._exercise_anchor_race(anchor_first=False)

    def _exercise_anchor_race(self, *, anchor_first):
        # TransactionTestCase flushes definitions created by data migrations.
        from types import SimpleNamespace

        from django.apps import apps

        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        site = Site.objects.create(domain="race.example.test", name="Race")
        actor = StaffUserFactory()
        actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="catalog", codename__in=["view_relationrecord", "add_relationrecord"]
            )
        )
        first, second, replacement = (
            CatalogEntity.objects.create(kind="crop", created_by=actor, provenance={"fixture": True}) for _ in range(3)
        )
        post = PostFactory(entity=first)
        grant = RelationSiteGrant.objects.create(actor=actor, site=site, can_edit=True)
        RelationEntityGrant.objects.create(grant=grant, entity=first, post=post)
        RelationEntityGrant.objects.create(grant=grant, entity=second)

        def draft():
            RelationAccess(actor, site.pk).save_draft(
                type_code="related_to", schema_version=1, participants={"member": [first.pk, second.pk]}
            )

        def reassign():
            type(post).objects.filter(pk=post.pk).update(entity=replacement)

        winner, waiting = (reassign, draft) if anchor_first else (draft, reassign)
        pids = Queue()

        def contender():
            close_old_connections()
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute("SET LOCAL lock_timeout = '7s'")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                    waiting()
                return "committed"
            except ValidationError as exc:
                return exc.code
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=1) as pool:
            with transaction.atomic(), connection.cursor() as cursor:
                winner()
                future = pool.submit(contender)
                pid = pids.get(timeout=6)
                deadline = monotonic() + 5
                while True:
                    cursor.execute("SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                    if future.done() or monotonic() >= deadline:
                        self.fail("Competing writer did not wait on the access scope")
                    sleep(0.01)
            self.assertEqual(future.result(timeout=8), "participant_unavailable" if anchor_first else "committed")
        self.assertEqual(RelationRecord.objects.count(), 0 if anchor_first else 1)
