import copy
import json
from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from api.v1.content.tests.test_catalog_relations import CatalogFixtures
from core.catalog import relation_service
from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.relations import ImportReceipt, RelationAuditEvent, RelationRecord, RelationRevision


class CatalogBulkTests(CatalogFixtures, TestCase):
    def setUp(self):
        self.setup_catalog()
        self.preview_url = reverse("catalog-batch-preview")
        self.apply_url = reverse("catalog-batch-apply")
        self.batch = {
            "operation": "drafts",
            "operation_key": "bulk-one",
            "items": [{"key": "one", "draft": copy.deepcopy(self.draft)}],
        }

    def preview(self, data=None):
        result = self.client.post(self.preview_url, data or self.batch, format="json")
        self.assertEqual(result.status_code, 200, result.data)
        return result

    def apply(self, preview):
        return self.client.post(
            self.apply_url,
            {"preview": preview.data["preview"], "payload_digest": preview.data["payload_digest"]},
            format="json",
        )

    def test_readonly_preview_atomic_apply_replay_and_existing_noop(self):
        preview = self.preview()
        self.assertTrue(preview.data["can_apply"])
        self.assertEqual(preview.data["items"][0]["effect"], "create")
        self.assertEqual(RelationRecord.objects.count(), 0)
        self.assertEqual(RelationRevision.objects.count(), 0)
        self.assertEqual(RelationAuditEvent.objects.count(), 0)
        self.assertEqual(ImportReceipt.objects.count(), 0)
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200, applied.data)
        replay = self.apply(preview)
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(applied.data, replay.data)
        self.assertEqual(replay["Idempotent-Replay"], "true")
        self.assertEqual(RelationRecord.objects.count(), 1)
        self.assertEqual(RelationRevision.objects.count(), 1)
        self.assertEqual(RelationAuditEvent.objects.get().actor_id, self.actor.pk)
        self.batch["operation_key"] = "second-key"
        duplicate = self.preview()
        self.assertEqual(duplicate.data["items"][0]["effect"], "noop")
        self.assertEqual(self.apply(duplicate).status_code, 200)
        self.assertEqual(RelationRevision.objects.count(), 1)

    def test_exact_in_batch_duplicates_fold_and_conflicting_sources_require_review(self):
        self.batch["items"].append({"key": "two", "draft": copy.deepcopy(self.draft)})
        preview = self.preview()
        self.assertEqual(preview.data["items"][1]["duplicate_of"], "one")
        result = self.apply(preview)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["results"][0]["record_id"], result.data["results"][1]["record_id"])
        self.assertEqual(RelationRevision.objects.count(), 1)
        self.batch["operation_key"] = "conflicting"
        self.batch["items"][1]["draft"]["source"] = {"different": "source"}
        conflict = self.preview()
        self.assertFalse(conflict.data["can_apply"])
        self.assertEqual(self.apply(conflict).status_code, 409)
        self.assertEqual(RelationRevision.objects.count(), 1)

    def test_changed_base_mapping_schema_input_and_expiration_require_new_preview(self):
        preview = self.preview()
        self.post.title += " changed"
        self.post.save(update_fields=["title"])
        stale = self.apply(preview)
        self.assertEqual(stale.status_code, 409, stale.data)
        self.assertEqual(stale.data["error"]["code"], "stale_preview")
        fresh = self.preview()
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 1000):
            expired = self.apply(fresh)
        self.assertEqual(expired.status_code, 409)
        self.assertEqual(expired.data["error"]["code"], "preview_expired")
        changed = self.client.post(
            self.apply_url, {"preview": fresh.data["preview"], "payload_digest": "a" * 64}, format="json"
        )
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(RelationRecord.objects.count(), 0)

    def test_permission_revoke_actor_site_binding_and_no_publish_from_drafts(self):
        preview = self.preview()
        self.site_grant.can_edit = False
        self.site_grant.save(update_fields=["can_edit"])
        self.assertEqual(self.apply(preview).status_code, 403)
        self.site_grant.can_edit = True
        self.site_grant.save(update_fields=["can_edit"])
        self.actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label="catalog", codename="add_relationrecord")
        )
        self.assertEqual(self.apply(preview).status_code, 403)
        self.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="add_relationrecord")
        )
        with self.settings.__class__(SITE_ID=self.other_site.pk):
            self.assertEqual(self.apply(preview).status_code, 403)
        self.batch["items"][0]["draft"]["status"] = "approved"
        rejected = self.client.post(self.preview_url, self.batch, format="json")
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(RelationRecord.objects.count(), 0)

    def test_atomic_rollback_if_second_write_fails(self):
        # Different types make two explicit nonduplicate logical records.
        self.batch["items"].append(
            {
                "key": "two",
                "draft": {
                    "type_code": "related_to",
                    "schema_version": 1,
                    "participants": {"member": [str(self.crop_entity.pk), str(self.cultivar_entity.pk)]},
                },
            }
        )
        preview = self.preview()
        original = relation_service.save_draft
        calls = []

        def fail_second(*args, **kwargs):
            calls.append(True)
            if len(calls) == 2:
                raise relation_service.RelationConflict("Synthetic late conflict")
            return original(*args, **kwargs)

        with patch("core.catalog.relation_service.save_draft", side_effect=fail_second):
            failed = self.apply(preview)
        self.assertEqual(failed.status_code, 409, failed.data)
        self.assertEqual(RelationRecord.objects.count(), 0)
        self.assertEqual(RelationRevision.objects.count(), 0)
        self.assertEqual(RelationAuditEvent.objects.count(), 0)
        self.assertEqual(ImportReceipt.objects.count(), 0)

    def test_explicit_revision_and_status_preview_revalidate_stale_etag(self):
        created = self.apply(self.preview()).data["results"][0]
        self.batch = {
            "operation": "drafts",
            "operation_key": "edit",
            "items": [
                {
                    "key": "one",
                    "record_id": created["record_id"],
                    "if_match": created["etag"],
                    "draft": {**self.draft, "payload": {"edited": True}},
                }
            ],
        }
        preview = self.preview()
        self.assertEqual(preview.data["items"][0]["effect"], "revise")
        result = self.apply(preview)
        self.assertEqual(result.status_code, 200, result.data)
        edited = result.data["results"][0]
        self.batch = {
            "operation": "submit",
            "operation_key": "submit",
            "items": [
                {
                    "key": "one",
                    "record_id": edited["record_id"],
                    "revision_id": edited["revision_id"],
                    "if_match": edited["etag"],
                }
            ],
        }
        preview = self.preview()
        self.assertEqual(RelationRevision.objects.order_by("number").last().state, "draft")
        result = self.apply(preview)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(RelationRevision.objects.order_by("number").last().state, "submitted")
        self.batch["operation_key"] = "stale"
        stale = self.preview()
        self.assertFalse(stale.data["can_apply"])
        self.assertEqual(self.apply(stale).status_code, 409)

    def test_limits_invalid_members_pagination_and_receipt_scope(self):
        self.batch["items"] = [{"key": f"item-{i:02d}", "draft": copy.deepcopy(self.draft)} for i in range(50)]
        preview = self.preview()
        result = self.apply(preview)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(result.data["count"], 50)
        self.assertEqual(len(result.data["results"]), 20)
        next_page = self.client.get(result.data["next"])
        self.assertEqual(next_page.status_code, 200)
        self.assertEqual(len(next_page.data["results"]), 20)
        final = self.client.get(next_page.data["next"])
        self.assertEqual(len(final.data["results"]), 10)
        self.batch["items"].append({"key": "too-many", "draft": copy.deepcopy(self.draft)})
        self.assertEqual(self.client.post(self.preview_url, self.batch, format="json").status_code, 400)
        self.cultivar.delete()
        receipt = self.client.get(reverse("catalog-batch-receipt", args=[result.data["receipt_id"]]))
        self.assertEqual(receipt.status_code, 404)
        self.assertEqual(self.apply(preview).status_code, 404)

    def test_admin_uses_same_preview_and_apply(self):
        self.client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        url = reverse("admin:catalog_relation_bulk")
        response = self.client.post(url, {"action": "preview", "batch": json.dumps(self.batch)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(RelationRecord.objects.count(), 0)
        plan = response.context["plan"]
        self.assertContains(response, "Apply reviewed batch")
        result = self.client.post(
            url, {"action": "apply", "preview": plan["preview"], "payload_digest": plan["payload_digest"]}
        )
        self.assertEqual(result.status_code, 302)
        self.assertContains(self.client.get(result.url), "bulk-one")
        self.assertEqual(RelationRecord.objects.count(), 1)

    def test_foreign_actor_cannot_apply_preview_or_read_receipt_and_expired_replay_is_stable(self):
        from rest_framework.authtoken.models import Token

        preview = self.preview()
        other = self.editor()
        grant = RelationSiteGrant.objects.create(actor=other, site=self.site, can_edit=True)
        for entity in (self.crop_entity, self.cultivar_entity):
            RelationEntityGrant.objects.create(grant=grant, entity=entity)
        token = Token.objects.create(user=other)
        original = self.token.key
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(self.apply(preview).status_code, 403)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {original}")
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200, applied.data)
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 1000):
            replay = self.apply(preview)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(applied.data, replay.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertEqual(
            self.client.get(reverse("catalog-batch-receipt", args=[applied.data["receipt_id"]])).status_code, 404
        )

    def test_existing_draft_edit_needs_change_without_implicit_add_permission(self):
        created = self.apply(self.preview()).data["results"][0]
        self.actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label="catalog", codename="add_relationrecord")
        )
        self.batch = {
            "operation": "drafts",
            "operation_key": "change-only",
            "items": [
                {
                    "key": "one",
                    "record_id": created["record_id"],
                    "if_match": created["etag"],
                    "draft": {**self.draft, "payload": {"edited": True}},
                }
            ],
        }
        preview = self.preview()
        self.assertTrue(preview.data["can_apply"], preview.data)
        self.assertEqual(self.apply(preview).status_code, 200)

    def test_preview_has_no_catalog_insert_update_or_delete_queries(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as queries:
            self.preview()
        mutations = [
            row["sql"]
            for row in queries.captured_queries
            if row["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) and "catalog_" in row["sql"]
        ]
        self.assertEqual(mutations, [])

    def test_bulk_lifecycle_uses_explicit_review_and_publish_permissions(self):
        self.publication_fixture()
        created = self.apply(self.preview()).data["results"][0]
        self.batch = {
            "operation": "submit",
            "operation_key": "submit-cycle",
            "items": [
                {
                    "key": "one",
                    "record_id": created["record_id"],
                    "revision_id": created["revision_id"],
                    "if_match": created["etag"],
                }
            ],
        }
        submitted = self.apply(self.preview())
        self.assertEqual(submitted.status_code, 200, submitted.data)
        self.batch["operation"] = "approve"
        self.batch["operation_key"] = "approve-cycle"
        self.batch["items"][0].update(if_match=submitted.data["results"][0]["etag"], content_locale="uk")
        self.assertEqual(self.client.post(self.preview_url, self.batch, format="json").status_code, 403)
        self.publication_rights(review=True, publish=True)
        approval_preview = self.preview()
        self.assertEqual(RelationRevision.objects.get().state, "submitted")
        approved = self.apply(approval_preview)
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(RelationRevision.objects.get().state, "approved")
        self.batch["operation"] = "publish"
        self.batch["operation_key"] = "publish-cycle"
        self.batch["items"][0]["if_match"] = approved.data["results"][0]["etag"]
        published = self.apply(self.preview())
        self.assertEqual(published.status_code, 200, published.data)
        self.assertTrue(RelationRecord.objects.get().releases.get().enabled)
        self.batch = {
            "operation": "archive",
            "operation_key": "archive-cycle",
            "items": [
                {"key": "one", "record_id": created["record_id"], "if_match": published.data["results"][0]["etag"]}
            ],
        }
        archive_preview = self.preview()
        self.assertFalse(RelationRecord.objects.get().archived)
        archived = self.apply(archive_preview)
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertTrue(RelationRecord.objects.get().archived)
        self.assertFalse(RelationRecord.objects.get().releases.get().enabled)

    def test_ungranted_participant_metadata_is_not_disclosed_by_validation(self):
        from uuid import uuid4

        from core.catalog.models import CatalogEntity

        hidden = CatalogEntity.objects.create(
            kind="disease", provenance={"private": "hidden witness"}, created_by=self.actor
        )
        errors = []
        for entity_id in (str(hidden.pk), str(uuid4())):
            data = copy.deepcopy(self.batch)
            data["items"][0]["draft"]["participants"]["crop"] = [entity_id]
            response = self.preview(data)
            self.assertFalse(response.data["can_apply"])
            errors.append(response.data["items"][0]["error"])
        self.assertEqual(errors[0], errors[1])
        self.assertEqual(errors[0]["code"], "participant_unavailable")
        self.assertEqual(RelationRecord.objects.count(), 0)

    def test_malformed_draft_reports_errors_without_server_failure_or_writes(self):
        for change in ({"payload": []}, {"source": []}, {"type_code": "missing"}, {"schema_version": 999}):
            data = copy.deepcopy(self.batch)
            data["items"][0]["draft"].update(change)
            response = self.preview(data)
            self.assertFalse(response.data["can_apply"])
            self.assertEqual(self.apply(response).status_code, 409)
        self.assertEqual(RelationRecord.objects.count(), 0)
        self.assertEqual(ImportReceipt.objects.count(), 0)

    def test_json_boolean_and_number_content_are_not_coalesced_as_noop(self):
        self.batch["items"][0]["draft"]["payload"] = {"flag": True}
        created = self.apply(self.preview())
        self.assertEqual(created.status_code, 200, created.data)
        self.batch["operation_key"] = "changed-json-type"
        self.batch["items"][0]["draft"]["payload"] = {"flag": 1}
        conflict = self.preview()
        self.assertFalse(conflict.data["can_apply"])
        self.assertEqual(conflict.data["items"][0]["error"]["code"], "source_conflict")
        self.assertEqual(RelationRevision.objects.count(), 1)


class ApplicationBulkTests(CatalogFixtures, TestCase):
    def setUp(self):
        from core.catalog.tests.test_applications import ApplicationTests

        ApplicationTests.setUp(self)
        self.preview_url = reverse("catalog-batch-preview")
        self.apply_url = reverse("catalog-batch-apply")
        self.batch = {
            "operation": "drafts",
            "operation_key": "app-batch",
            "items": [{"key": "app", "draft": copy.deepcopy(self.draft)}],
        }

    def participant(self, *args, **kwargs):
        from core.catalog.tests.test_applications import ApplicationTests

        return ApplicationTests.participant(self, *args, **kwargs)

    def grant_review(self):
        from core.catalog.tests.test_applications import ApplicationTests

        return ApplicationTests.grant_review(self)

    def grant_global_actions(self):
        from core.catalog.tests.test_applications import ApplicationTests

        return ApplicationTests.grant_global_actions(self)

    preview = CatalogBulkTests.preview
    apply = CatalogBulkTests.apply

    def test_application_drafts_use_typed_validator_and_exact_repeat_is_noop(self):
        from core.catalog.application_models import PlantProtectionApplicationDetails

        preview = self.preview()
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 0)
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200, applied.data)
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 1)
        self.batch["operation_key"] = "app-repeat"
        repeat = self.preview()
        self.assertEqual(repeat.data["items"][0]["effect"], "noop")
        self.assertEqual(self.apply(repeat).status_code, 200)
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 1)
        self.batch["operation_key"] = "other-method"
        self.batch["items"][0]["draft"]["payload"]["method"] = "soil_application"
        changed = self.preview()
        self.assertEqual(changed.data["items"][0]["effect"], "create")
        self.assertEqual(self.apply(changed).status_code, 200)
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 2)

    def approved_record(self, key="create-one"):
        # Country grant is created once, then reused by later explicit reviews.
        from core.catalog.application_models import ApplicationReviewerGrant

        if not ApplicationReviewerGrant.objects.filter(site_grant=self.site_grant, country=self.country).exists():
            self.grant_review()
        created = self.create(key).data["record"]
        record = self.action("catalog-submit", created, revision=True).data["record"]
        reviewed = self.action("catalog-review", record, {"action": "approve", "content_locale": "uk"}, revision=True)
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        record = reviewed.data["record"]
        released = self.action(
            "catalog-release", record, {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        )
        self.assertEqual(released.status_code, 200, released.data)
        return released.data["record"]

    def source_batch(self, record, *, complete=True, scopes=None):
        revision = RelationRevision.objects.get(pk=record["latest_revision"]["id"])
        return {
            "operation": "withdraw_source",
            "operation_key": "source-withdraw",
            "items": [
                {
                    "key": "source",
                    "type_code": revision.record.relation_type_id,
                    "country": revision.country,
                    "source_version_digest": revision.source_version_digest,
                    "reason": "Synthetic document withdrawal",
                    "evidence": {"review": "synthetic source decision"},
                    "scope_complete": complete,
                    "affected_versions": {record["id"]: record["lock_version"]},
                    "scope_versions": scopes or {},
                }
            ],
        }

    def test_source_withdrawal_is_previewed_atomic_and_blocks_future_import(self):
        from core.catalog.relations import SourceWithdrawalGate

        record = self.approved_record()
        self.grant_global_actions()
        self.batch = self.source_batch(record)
        preview = self.preview()
        self.assertTrue(preview.data["can_apply"], preview.data)
        self.assertFalse(SourceWithdrawalGate.objects.exists())
        self.assertFalse(RelationRecord.objects.get().withdrawn)
        result = self.apply(preview)
        self.assertEqual(result.status_code, 200, result.data)
        self.assertEqual(SourceWithdrawalGate.objects.count(), 1)
        self.assertTrue(RelationRecord.objects.get().withdrawn)
        self.assertFalse(RelationRecord.objects.get().releases.get().enabled)
        replay = self.apply(preview)
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(result.data, replay.data)
        self.assertEqual(RelationRecord.objects.get().eligibility_epoch, 1)
        self.batch = {
            "operation": "drafts",
            "operation_key": "blocked-import",
            "items": [{"key": "app", "draft": copy.deepcopy(self.draft)}],
        }
        self.batch["items"][0]["draft"]["payload"]["method"] = "soil_application"
        blocked = self.preview()
        self.assertFalse(blocked.data["can_apply"])
        self.assertEqual(self.apply(blocked).status_code, 409)
        self.assertEqual(RelationRecord.objects.count(), 1)

    def test_incomplete_source_scope_quarantines_other_sources_until_reviewed_reconciliation(self):
        from core.catalog.relations import RelationScopeGate, SourceWithdrawalGate

        first = self.approved_record()
        self.draft["payload"]["method"] = "soil_application"
        self.draft["source"]["version"] = "2"
        second = self.approved_record("second-source")
        self.grant_global_actions()
        scope_versions = {first["id"]: first["lock_version"], second["id"]: second["lock_version"]}
        self.batch = self.source_batch(first, complete=False, scopes=scope_versions)
        denied = self.client.post(self.preview_url, self.batch, format="json")
        self.assertEqual(denied.status_code, 403)
        self.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="review_shared_relations")
        )
        preview = self.preview()
        self.assertTrue(preview.data["can_apply"], preview.data)
        applied = self.apply(preview)
        self.assertEqual(applied.status_code, 200, applied.data)
        self.assertTrue(RelationScopeGate.objects.get().quarantined)
        self.assertFalse(any(RelationRecord.objects.get(pk=pk).releases.get().enabled for pk in scope_versions))
        current = {str(record.pk): record.lock_version for record in RelationRecord.objects.all()}
        self.batch = {
            "operation": "reconcile_source",
            "operation_key": "reconcile",
            "items": [
                {
                    "key": "scope",
                    "type_code": "plant_protection_application",
                    "country": "UA",
                    "if_match": applied.data["results"][0]["scope_etag"],
                    "affected_versions": current,
                    "evidence": {"review": "complete synthetic country-source manifest"},
                }
            ],
        }
        fresh = self.preview()
        self.assertTrue(fresh.data["can_apply"], fresh.data)
        reconciled = self.apply(fresh)
        self.assertEqual(reconciled.status_code, 200, reconciled.data)
        self.assertFalse(RelationScopeGate.objects.get().quarantined)
        self.assertEqual(SourceWithdrawalGate.objects.count(), 1)
        self.assertFalse(any(RelationRecord.objects.get(pk=pk).releases.get().enabled for pk in scope_versions))


class CatalogBulkConcurrencyTests(CatalogFixtures, TransactionTestCase):
    def setUp(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        self.setup_catalog()

    def test_two_connections_apply_one_preview_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections
        from rest_framework.test import APIClient

        data = {
            "operation": "drafts",
            "operation_key": "concurrent-bulk",
            "items": [{"key": "one", "draft": self.draft}],
        }
        preview = self.client.post(reverse("catalog-batch-preview"), data, format="json")
        self.assertEqual(preview.status_code, 200, preview.data)
        payload = {"preview": preview.data["preview"], "payload_digest": preview.data["payload_digest"]}
        barrier = Barrier(2)
        token = self.token.key

        def apply():
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
                barrier.wait(timeout=10)
                response = client.post(reverse("catalog-batch-apply"), payload, format="json")
                return response.status_code, response.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: apply(), range(2)))
        self.assertEqual([status for status, _ in outcomes], [200, 200], outcomes)
        self.assertEqual(outcomes[0][1], outcomes[1][1])
        self.assertEqual(RelationRecord.objects.count(), 1)
        self.assertEqual(RelationRevision.objects.count(), 1)
        self.assertEqual(RelationAuditEvent.objects.count(), 1)
        self.assertEqual(ImportReceipt.objects.count(), 1)


class ApplicationBulkConcurrencyTests(CatalogFixtures, TransactionTestCase):
    participant = ApplicationBulkTests.participant
    grant_review = ApplicationBulkTests.grant_review
    grant_global_actions = ApplicationBulkTests.grant_global_actions
    approved_record = ApplicationBulkTests.approved_record
    source_batch = ApplicationBulkTests.source_batch
    preview = CatalogBulkTests.preview
    apply = CatalogBulkTests.apply

    def setUp(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        ApplicationBulkTests.setUp(self)

    def test_source_withdrawal_and_import_race_cannot_commit_a_partial_scope(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections
        from rest_framework.test import APIClient

        from core.catalog.relations import SourceWithdrawalGate

        record = self.approved_record()
        self.grant_global_actions()
        source_payload = self.source_batch(record)
        source_preview = self.preview(source_payload)
        draft = copy.deepcopy(self.draft)
        draft["payload"]["method"] = "soil_application"
        import_payload = {
            "operation": "drafts",
            "operation_key": "parallel-import",
            "items": [{"key": "second", "draft": draft}],
        }
        import_preview = self.preview(import_payload)
        barrier = Barrier(2)
        token = self.token.key

        def apply(preview):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
                barrier.wait(timeout=10)
                response = client.post(
                    reverse("catalog-batch-apply"),
                    {"preview": preview.data["preview"], "payload_digest": preview.data["payload_digest"]},
                    format="json",
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(apply, [source_preview, import_preview]))
        self.assertEqual(sorted(outcomes), [200, 409], outcomes)
        if not SourceWithdrawalGate.objects.exists():
            source_payload["items"][0]["affected_versions"] = {
                str(row.pk): row.lock_version for row in RelationRecord.objects.all()
            }
            retry = self.apply(self.preview(source_payload))
            self.assertEqual(retry.status_code, 200, retry.data)
        self.assertEqual(SourceWithdrawalGate.objects.count(), 1)
        self.assertTrue(all(row.withdrawn for row in RelationRecord.objects.all()))
        self.assertFalse(any(row.releases.filter(enabled=True).exists() for row in RelationRecord.objects.all()))
