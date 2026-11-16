from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from queue import Queue
from time import monotonic, sleep

from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, close_old_connections, connection, transaction
from django.db.models import F
from django.test import TransactionTestCase

from core.catalog.models import CatalogEntity
from core.catalog.relation_service import (
    RelationConflict,
    correct_identity,
    reconcile_source_scope,
    reinstate_record,
    review_revision,
    save_draft,
    set_presentation_selection,
    set_release,
    withdraw_record,
    withdraw_source,
)
from core.catalog.relations import (
    RelationParticipant,
    RelationRecord,
    RelationRelease,
    RelationScopeGate,
    RelationType,
    RelationTypeVersion,
    SourceWithdrawalGate,
)
from core.utils.tests.factories import CategoryFactory, PostFactory, UserFactory


class RelationTests(TransactionTestCase):
    def setUp(self):
        from types import SimpleNamespace

        from django.apps import apps

        bootstrap = import_module("core.catalog.migrations.0005_relation_definitions").bootstrap
        bootstrap(apps, SimpleNamespace(connection=connection))
        bootstrap(apps, SimpleNamespace(connection=connection))
        self.assertEqual(
            RelationTypeVersion.objects.filter(relation_type_id__in=["related_to", "cultivar_of"]).count(), 2
        )
        self.actor = UserFactory()
        self.crop = self.entity("crop")
        self.cultivar = self.entity("cultivar")
        self.other = self.entity("crop")

    def entity(self, kind):
        return CatalogEntity.objects.create(kind=kind, created_by=self.actor, provenance={"source": "synthetic"})

    def draft(self, **kwargs):
        return save_draft(
            type_code="cultivar_of",
            schema_version=1,
            participants={"cultivar": [self.cultivar.pk], "crop": [kwargs.pop("crop", self.crop).pk]},
            actor=self.actor,
            **kwargs,
        )

    def review(self, revision, action):
        return review_revision(
            record_id=revision.record_id,
            revision_id=revision.pk,
            action=action,
            actor=self.actor,
            expected_version=self.version(revision),
        )

    def version(self, revision):
        return RelationRecord.objects.get(pk=revision.record_id).lock_version

    def release(self, revision, site):
        return set_release(
            record_id=revision.record_id,
            revision_id=revision.pk,
            expected_version=self.version(revision),
            site=site,
            actor=self.actor,
            enabled=True,
        )

    def test_immutable_revision_and_scoped_presentation(self):
        post = PostFactory(entity=self.cultivar)
        site = Site.objects.create(domain="example.test", name="fixture")
        selection = set_presentation_selection(
            site=site,
            content_locale="uk",
            entity=self.cultivar,
            anchor=post,
            expected_version=None,
            actor=self.actor,
            approved=False,
        )
        self.assertFalse(selection.approved)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(post).objects.filter(pk=post.pk).update(entity=self.crop)
        category = CategoryFactory()
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(category).objects.filter(pk=category.pk).update(entity=self.cultivar)
        revision = self.draft()
        with self.assertRaises(IntegrityError), transaction.atomic():
            RelationParticipant.objects.filter(revision=revision, role="crop").update(entity=self.other)
        with self.assertRaises(IntegrityError), transaction.atomic():
            type(revision).objects.filter(pk=revision.pk).update(payload={"bypass": True})
        with self.assertRaises(ValidationError):
            save_draft(
                type_code="cultivar_of",
                schema_version=1,
                participants={"cultivar": [self.crop.pk]},
                actor=self.actor,
            )

    def test_approval_withdrawal_and_pending_revision(self):
        site = Site.objects.create(domain="example.test", name="fixture")
        site2 = Site.objects.create(domain="other.test", name="fixture")
        revision = self.draft()
        self.review(revision, "submit")
        self.review(revision, "approve")
        live = self.release(revision, site)
        self.release(revision, site2)
        previous_version = self.version(revision)
        pending = self.draft(record_id=revision.record_id, expected_version=previous_version, crop=self.other)
        live.refresh_from_db()
        self.assertEqual(live.approved_revision_id, revision.pk)
        with self.assertRaises(RelationConflict):
            review_revision(
                record_id=revision.record_id,
                revision_id=pending.pk,
                action="submit",
                actor=self.actor,
                expected_version=previous_version,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RelationRelease.objects.filter(pk=live.pk).update(
                approved_revision=pending, lock_version=F("lock_version") + 1
            )
        withdrawal = withdraw_record(
            record_id=revision.record_id,
            expected_version=self.version(revision),
            actor=self.actor,
            reason="Fixture withdrawal",
            operation_key="withdraw-once",
            evidence={"source": "withdrawal"},
        )
        self.assertCountEqual(withdrawal.affected_site_ids, [site.pk, site2.pk])
        self.assertFalse(RelationRelease.objects.filter(record_id=revision.record_id, enabled=True).exists())
        with self.assertRaises(RelationConflict):
            self.review(pending, "submit")
        replacement = self.draft(record_id=revision.record_id, expected_version=self.version(revision))
        self.review(replacement, "submit")
        self.review(replacement, "approve")
        reinstate_record(
            record_id=revision.record_id,
            revision_id=replacement.pk,
            withdrawal_id=withdrawal.pk,
            expected_version=self.version(revision),
            actor=self.actor,
            evidence={"source": "new evidence"},
        )
        self.assertFalse(RelationRelease.objects.filter(record_id=revision.record_id, enabled=True).exists())
        with self.assertRaises(RelationConflict):
            self.release(revision, site)
        self.release(replacement, site)

    def test_direct_writes_cannot_seal_incomplete_or_mismatched_revision(self):
        original = self.draft()
        model = type(original)
        for participants in (
            [("cultivar", self.cultivar)],
            [("cultivar", self.crop), ("crop", self.other)],
            [("cultivar", self.entity("cultivar")), ("crop", self.crop)],
        ):
            with self.subTest(participants=participants), self.assertRaises(IntegrityError), transaction.atomic():
                revision = model.objects.create(
                    record=original.record,
                    number=2,
                    schema=original.schema,
                    created_epoch=0,
                    created_by=self.actor,
                )
                RelationParticipant.objects.bulk_create(
                    [
                        RelationParticipant(revision=revision, role=role, entity=entity, ordinal=0)
                        for role, entity in participants
                    ]
                )
                revision.sealed = True
                revision.save(update_fields=["sealed"])

    def test_reversed_symmetric_pair_concurrent_creation(self):
        def create_pair(ids):
            close_old_connections()
            try:
                save_draft(type_code="related_to", schema_version=1, participants={"member": ids}, actor=self.actor)
                return "created"
            except RelationConflict as exc:
                return exc.code
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(create_pair, [(self.crop.pk, self.other.pk), (self.other.pk, self.crop.pk)]))
        self.assertCountEqual(outcomes, ["created", "duplicate_relation"])
        self.assertEqual(RelationRecord.objects.filter(relation_type_id="related_to").count(), 1)

    def test_identity_correction_is_atomic_unique_and_replayable(self):
        original = save_draft(
            type_code="related_to",
            schema_version=1,
            participants={"member": [self.crop.pk, self.cultivar.pk]},
            actor=self.actor,
        )
        self.review(original, "submit")
        self.review(original, "approve")
        site = Site.objects.create(domain="example.test", name="fixture")
        self.release(original, site)
        args = {
            "record_id": original.record_id,
            "expected_version": self.version(original),
            "schema_version": 1,
            "participants": {"member": [self.crop.pk, self.other.pk]},
            "actor": self.actor,
            "reason": "Correct target",
            "evidence": {"source": "fixture"},
            "operation_key": "correction-1",
            "payload": {},
            "source": {},
        }
        with self.assertRaises(RelationConflict):
            save_draft(
                type_code="related_to",
                schema_version=1,
                participants=args["participants"],
                actor=self.actor,
                record_id=original.record_id,
                expected_version=args["expected_version"],
            )
        corrected = correct_identity(**args)
        self.assertEqual(correct_identity(**args).pk, corrected.pk)
        self.assertFalse(RelationRelease.objects.get(record_id=original.record_id).enabled)
        self.assertEqual(corrected.successor.revisions.get().state, "draft")
        with self.assertRaises(RelationConflict):
            save_draft(
                type_code="related_to",
                schema_version=1,
                participants=args["participants"],
                actor=self.actor,
            )
        with self.assertRaises(IntegrityError), transaction.atomic():
            RelationRecord.objects.filter(pk=corrected.successor_id).update(
                superseded_by_id=original.record_id,
                withdrawn=True,
                archived=True,
            )

    def test_source_quarantine_prevents_future_import_and_old_release(self):
        digest = "a" * 64
        revision = self.draft(country="UA", source_version_digest=digest)
        self.review(revision, "submit")
        self.review(revision, "approve")
        site = Site.objects.create(domain="example.test", name="fixture")
        self.release(revision, site)
        withdraw_source(
            type_code="cultivar_of",
            country="UA",
            digest=digest,
            reason="Withdrawn document",
            evidence={"source": "fixture"},
            actor=self.actor,
            scope_complete=False,
            affected_versions={str(revision.record_id): self.version(revision)},
        )
        self.assertFalse(RelationRelease.objects.get(record_id=revision.record_id).enabled)
        args = {"record_id": revision.record_id, "expected_version": self.version(revision), "country": "UA"}
        with self.assertRaises(RelationConflict):
            self.draft(**args, source_version_digest="b" * 64)
        reconcile_source_scope(
            type_code="cultivar_of",
            country="UA",
            expected_version=1,
            actor=self.actor,
            evidence={"manifest": "reviewed"},
        )
        with self.assertRaises(RelationConflict):
            self.draft(**args, source_version_digest=digest)
        self.draft(**args, source_version_digest="b" * 64)

    def test_three_party_relations_use_the_same_role_and_identity_validation(self):
        fixture = RelationType.objects.create(code="synthetic_three_party")
        roles = {
            "item": {"min": 1, "max": 1, "kinds": ["preparation"]},
            "crop": {"min": 1, "max": 1, "kinds": ["crop"]},
            "target": {"min": 1, "max": 1, "kinds": ["disease"]},
        }
        RelationTypeVersion.objects.create(
            relation_type=fixture,
            version=1,
            roles=roles,
            identity_roles=list(roles),
            identity_fields=["method"],
        )
        item, target = self.entity("preparation"), self.entity("disease")
        participants = {"item": [item.pk], "crop": [self.crop.pk], "target": [target.pk]}
        args = {"type_code": fixture.pk, "schema_version": 1, "participants": participants, "actor": self.actor}
        first = save_draft(**args, payload={"method": "fixture-one"})
        second = save_draft(**args, payload={"method": "fixture-two"})
        self.assertNotEqual(first.record_id, second.record_id)
        self.assertEqual(first.participants.count(), 3)
        with self.assertRaises(RelationConflict):
            save_draft(**args, payload={"method": "fixture-one"})
        with self.assertRaises(ValidationError):
            save_draft(
                **(args | {"participants": participants | {"target": [self.other.pk]}}),
                payload={"method": "fixture-three"},
            )

    def test_direct_withdrawal_and_reinstatement_require_matching_history(self):
        revision = self.draft()
        self.review(revision, "submit")
        self.review(revision, "approve")
        site = Site.objects.create(domain="withdraw.example.test", name="fixture")
        release = self.release(revision, site)
        records = RelationRecord.objects.filter(pk=revision.record_id)
        for kwargs in ({}, {"eligibility_epoch": 1, "lock_version": F("lock_version") + 1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(IntegrityError), transaction.atomic():
                RelationRelease.objects.filter(pk=release.pk).update(enabled=False, lock_version=F("lock_version") + 1)
                records.update(withdrawn=True, **kwargs)
        release.refresh_from_db()
        self.assertTrue(release.enabled)
        withdraw_record(
            record_id=revision.record_id,
            expected_version=self.version(revision),
            actor=self.actor,
            reason="Fixture withdrawal",
            operation_key="direct-reinstatement",
            evidence={"source": "fixture"},
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            records.update(withdrawn=False, lock_version=F("lock_version") + 1)
        with self.assertRaises(RelationConflict):
            self.release(revision, site)
        self.assertTrue(records.get().withdrawn)
        self.assertFalse(RelationRelease.objects.get(pk=release.pk).enabled)

    def _check_serialization(self, winner, contender, isolation):
        pids = Queue()

        def write():
            close_old_connections()
            try:
                with transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(f"SET TRANSACTION ISOLATION LEVEL {isolation}")
                    cursor.execute("SET LOCAL lock_timeout = '7s'")
                    # Force the competing statement to begin with its own snapshot.
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.put(cursor.fetchone()[0])
                    contender()
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            except DatabaseError as error:
                return error.__cause__.sqlstate
            finally:
                connection.close()
            return "committed"

        with ThreadPoolExecutor(max_workers=1) as executor:
            with transaction.atomic(), connection.cursor() as cursor:
                winner()
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                future = executor.submit(write)
                pid = pids.get(timeout=6)
                deadline = monotonic() + 5
                while True:
                    cursor.execute("SELECT pg_backend_pid() = ANY(pg_blocking_pids(%s))", [pid])
                    if cursor.fetchone()[0]:
                        break
                    if future.done() or monotonic() >= deadline:
                        self.fail("Competing transaction did not wait on the eligibility writer")
                    sleep(0.01)
            return future.result(timeout=8)

    def test_direct_release_serializes_with_gate_writes_in_both_orders(self):
        matrix = [
            ("source", True, "READ COMMITTED", "23514"),
            ("source", False, "READ COMMITTED", "23514"),
            ("scope", True, "READ COMMITTED", "23514"),
            ("scope", False, "READ COMMITTED", "23514"),
            ("source", True, "REPEATABLE READ", "40001"),
        ]
        for index, (gate_kind, gate_first, isolation, rejected) in enumerate(matrix):
            with self.subTest(gate=gate_kind, gate_first=gate_first, isolation=isolation):
                country = "A" + chr(ord("A") + index)
                digest = f"{index:064x}"
                self.cultivar = self.entity("cultivar")
                revision = self.draft(country=country, source_version_digest=digest)
                self.review(revision, "submit")
                self.review(revision, "approve")
                site = Site.objects.create(domain=f"race-{index}.example.test", name="fixture")

                def make_source(source_digest):
                    return SourceWithdrawalGate.objects.create(
                        relation_type_id="cultivar_of",
                        country=country,
                        source_version_digest=source_digest,
                        evidence={"fixture": True},
                        actor=self.actor,
                    )

                def write_release():
                    RelationRelease.objects.create(
                        site=site,
                        record_id=revision.record_id,
                        approved_revision_id=revision.pk,
                        enabled=True,
                    )

                if gate_kind == "scope":
                    # The scope gate must also reject a different version within the same country.
                    source = make_source("f" * 64)

                    def write_gate():
                        RelationScopeGate.objects.create(
                            relation_type_id="cultivar_of",
                            country=country,
                            source_id=source.pk,
                            quarantined=True,
                        )

                    gates = RelationScopeGate.objects.filter(relation_type_id="cultivar_of", country=country)
                else:

                    def write_gate():
                        make_source(digest)

                    gates = SourceWithdrawalGate.objects.filter(
                        relation_type_id="cultivar_of",
                        country=country,
                        source_version_digest=digest,
                    )

                winner, contender = (write_gate, write_release) if gate_first else (write_release, write_gate)
                self.assertEqual(self._check_serialization(winner, contender, isolation), rejected)
                self.assertEqual(gates.exists(), gate_first)
                self.assertEqual(RelationRelease.objects.filter(site=site, enabled=True).exists(), not gate_first)
