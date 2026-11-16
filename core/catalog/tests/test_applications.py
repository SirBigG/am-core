import copy
from datetime import timedelta
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from api.v1.content.tests.test_catalog_relations import CatalogFixtures
from core.catalog.access_models import RelationEntityGrant
from core.catalog.application_models import (
    ApplicationCountryPolicy,
    ApplicationReviewerGrant,
    PlantProtectionApplicationDetails,
)
from core.catalog.applications import APPLICATION_TYPE, require_evidence
from core.catalog.models import CatalogEntity
from core.catalog.relation_access import RelationAccess
from core.catalog.relation_service import review_revision
from core.catalog.relations import (
    EntityPresentationSelection,
    ImportReceipt,
    RelationAuditEvent,
    RelationParticipant,
    RelationRecord,
    RelationRevision,
    RelationTypeVersion,
)
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest
from core.utils.tests.factories import PostFactory


class ApplicationTests(CatalogFixtures, TestCase):
    def setUp(self):
        import_module("core.catalog.migrations.0010_application_definition_guards").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        self.setup_catalog()
        self.publication_fixture()
        self.publication_rights(review=True, publish=True)
        self.country = ApplicationCountryPolicy.objects.create(country="UA", timezone_name="Europe/Kyiv", active=True)
        self.preparation = self.participant("preparation", "Synthetic formulation A")
        self.target = self.participant("disease", "Synthetic exact target")
        today = timezone.now().date()
        self.draft = {
            "type_code": APPLICATION_TYPE,
            "schema_version": 1,
            "participants": {
                "preparation": [str(self.preparation.pk)],
                "crop": [str(self.crop_entity.pk)],
                "target": [str(self.target.pk)],
            },
            "payload": {
                "country": "UA",
                "method": "foliar_spray",
                "formulation_identity": "synthetic-formulation-A",
                "formulation_verified": True,
                "formulation_provenance": {"reference": "synthetic verified formulation"},
                "target_kind": "disease",
                "target_locator": "",
                "registration_authority": "synthetic-authority",
                "registration_record_key": "synthetic-registration",
                "application_locator": "application-1",
                "checked_at": (timezone.now() - timedelta(minutes=1)).isoformat(),
                "valid_from": (today - timedelta(days=1)).isoformat(),
                "valid_until": (today + timedelta(days=1)).isoformat(),
                "regulatory_decision": "confirmed",
                "regulatory_provenance": {"reference": "synthetic decision"},
            },
            "source": {
                "reference": "urn:agromega:synthetic-source",
                "document": "Synthetic document",
                "version": "1",
                "content_digest": "a" * 64,
            },
        }

    def participant(self, kind, title):
        entity = CatalogEntity.objects.create(
            kind=kind,
            provenance={
                "synthetic": True,
                **({"formulation_identity": "synthetic-formulation-A"} if kind == "preparation" else {}),
            },
            created_by=self.actor,
        )
        post = PostFactory(title=title, entity=entity, rubric=self.category)
        post.get_absolute_url()
        post.refresh_from_db()
        RelationEntityGrant.objects.create(grant=self.site_grant, entity=entity, post=post)
        approval = PostPublicationApproval.objects.create(
            post=post,
            content_digest=material_digest(post),
            content_locale="uk",
            reviewed_by=self.actor,
            reviewed_at=timezone.now(),
            language_verified=True,
            provenance={"synthetic": True},
        )
        SitePostPublication.objects.create(
            site=self.site,
            post=post,
            approval=approval,
            content_locale="uk",
            category=self.category,
            canonical_path=post.absolute_url,
            enabled=True,
            publish_at=timezone.now(),
        )
        EntityPresentationSelection.objects.create(
            site=self.site, entity=entity, post=post, content_locale="uk", approved=True, updated_by=self.actor
        )
        return entity

    def grant_review(self):
        self.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="review_plant_protection_applications")
        )
        ApplicationReviewerGrant.objects.create(site_grant=self.site_grant, country=self.country, can_review=True)

    def approve(self, record):
        self.grant_review()
        submitted = self.action("catalog-submit", record, revision=True)
        self.assertEqual(submitted.status_code, 200, submitted.data)
        response = self.action(
            "catalog-review", submitted.data["record"], {"action": "approve", "content_locale": "uk"}, revision=True
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["record"]

    def test_api_domain_lifecycle_and_current_site_release(self):
        record = self.create().data["record"]
        revision = RelationRevision.objects.get()
        self.assertEqual(revision.country, "UA")
        self.assertEqual(len(revision.source_version_digest), 64)
        details = PlantProtectionApplicationDetails.objects.get()
        self.assertEqual(details.revision_id, revision.pk)
        self.assertEqual(details.method_id, "foliar_spray")
        record = self.approve(record)
        release = self.action(
            "catalog-release", record, {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        )
        self.assertEqual(release.status_code, 200, release.data)
        self.assertTrue(release.data["record"]["release"]["enabled"])
        archived = self.action("catalog-archive", release.data["record"])
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertFalse(archived.data["record"]["release"]["enabled"])
        self.assertEqual(RelationAuditEvent.objects.filter(actor=self.actor).count(), 5)

    def test_unresolved_group_is_literal_and_methods_remain_distinct(self):
        self.draft["participants"].pop("target")
        self.draft["payload"].update(
            target_kind="pest", target_locator="source-group-1", target_text="Synthetic pest group"
        )
        first = self.create().data["record"]
        self.assertEqual(first["latest_revision"]["participants"].get("target"), None)
        self.draft["payload"]["method"] = "soil_application"
        second = self.create("other-method").data["record"]
        self.assertNotEqual(first["id"], second["id"])
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 2)
        replay = self.create("other-method")
        self.assertEqual(replay.data["record"]["id"], second["id"])
        self.assertEqual(RelationParticipant.objects.filter(role="target").count(), 0)

    def test_country_and_domain_review_authority_are_explicit(self):
        record = self.create().data["record"]
        submitted = self.action("catalog-submit", record, revision=True).data["record"]
        data = {"action": "approve", "content_locale": "uk"}
        self.assertEqual(self.action("catalog-review", submitted, data, revision=True).status_code, 403)
        self.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="review_plant_protection_applications")
        )
        self.assertEqual(self.action("catalog-review", submitted, data, revision=True).status_code, 403)
        ApplicationReviewerGrant.objects.create(site_grant=self.site_grant, country=self.country, can_review=True)
        self.assertEqual(self.action("catalog-review", submitted, data, revision=True).status_code, 200)

    def test_unknown_evidence_cannot_be_approved_and_source_edit_is_new_draft(self):
        self.draft["payload"].update(
            formulation_verified=None,
            formulation_provenance={},
            valid_until=None,
            regulatory_decision="unresolved",
            regulatory_provenance={},
        )
        record = self.create().data["record"]
        self.grant_review()
        submitted = self.action("catalog-submit", record, revision=True).data["record"]
        response = self.action(
            "catalog-review", submitted, {"action": "approve", "content_locale": "uk"}, revision=True
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(RelationRevision.objects.get().state, "submitted")
        self.draft["source"]["version"] = "2"
        self.draft["source"]["content_digest"] = "b" * 64
        edited = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            self.draft,
            format="json",
            headers={"if-match": submitted["etag"], "idempotency-key": "new-source"},
        )
        self.assertEqual(edited.status_code, 201, edited.data)
        revisions = list(RelationRevision.objects.order_by("number"))
        self.assertNotEqual(revisions[0].source_version_digest, revisions[1].source_version_digest)
        self.assertEqual(revisions[1].state, "draft")
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 2)

    def test_identity_changes_require_correction(self):
        record = self.create().data["record"]
        for field, value in (
            ("method", "soil_application"),
            ("formulation_identity", "different-formulation"),
            ("application_locator", "other-regulation"),
        ):
            body = copy.deepcopy(self.draft)
            body["payload"][field] = value
            response = self.client.post(
                reverse("catalog-revisions", args=[record["id"]]),
                body,
                format="json",
                headers={"if-match": record["etag"], "idempotency-key": field},
            )
            self.assertEqual(response.status_code, 409, response.data)
            self.assertEqual(response.data["error"]["code"], "identity_change_requires_correction")
        self.assertEqual(RelationRevision.objects.count(), 1)

    def test_invalid_domain_values_are_atomic_validation_errors(self):
        for field, value in (
            ("method", "unknown"),
            ("valid_from", "invalid-date"),
            ("valid_until", 0),
            ("formulation_verified", "yes"),
            ("target_kind", "pest"),
            ("target_locator", None),
            ("dose_min", 0),
            ("checked_at", (timezone.now() + timedelta(days=1)).isoformat()),
        ):
            body = copy.deepcopy(self.draft)
            body["payload"][field] = value
            response = self.client.post(self.url, body, format="json", headers={"idempotency-key": field})
            self.assertEqual(response.status_code, 400, response.data)
            self.assertEqual(RelationRevision.objects.count(), 0)
            self.assertEqual(ImportReceipt.objects.count(), 0)

    def test_country_calendar_expiry_rechecks_without_saving(self):
        record = self.approve(self.create().data["record"])
        revision = RelationRevision.objects.get(pk=record["latest_revision"]["id"])
        details = revision.application
        with transaction.atomic():
            with patch("core.catalog.applications.timezone.now", return_value=timezone.now() + timedelta(days=4)):
                with self.assertRaises(ValidationError):
                    require_evidence(revision, current=True)
            require_evidence(revision, current=True)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        self.country.active = False
        self.country.save(update_fields=["active"])
        response = self.action("catalog-release", record, {"revision_id": str(revision.pk), "content_locale": "uk"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(details.valid_until, revision.application.valid_until)

    def test_postgresql_details_immutable_and_missing_projection_rejected(self):
        self.create()
        revision = RelationRevision.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            PlantProtectionApplicationDetails.objects.filter(revision=revision).update(formulation_verified=False)
        with self.assertRaises(IntegrityError), transaction.atomic():
            pending = RelationRevision.objects.create(
                record=revision.record,
                number=2,
                schema=revision.schema,
                payload=revision.payload,
                source=revision.source,
                country=revision.country,
                source_version_digest=revision.source_version_digest,
                created_epoch=0,
                created_by=self.actor,
            )
            RelationParticipant.objects.bulk_create(
                [
                    RelationParticipant(revision=pending, role=p.role, entity=p.entity, ordinal=p.ordinal)
                    for p in revision.participants.all()
                ]
            )
            pending.sealed = True
            pending.save(update_fields=["sealed"])
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.assertEqual(RelationRevision.objects.count(), 1)

    def test_postgresql_cannot_approve_incomplete_domain_evidence(self):
        self.draft["payload"]["formulation_verified"] = None
        record = self.create().data["record"]
        revision = RelationRevision.objects.get()
        access = RelationAccess(self.actor, self.site.pk)
        access.submit(record_id=revision.record_id, revision_id=revision.pk, expected_version=record["lock_version"])
        revision.record.refresh_from_db()
        with self.assertRaises(IntegrityError), transaction.atomic():
            review_revision(
                record_id=revision.record_id,
                revision_id=revision.pk,
                expected_version=revision.record.lock_version,
                action="approve",
                actor=self.actor,
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_existing_admin_uses_application_schema_and_evidence_history(self):
        self.client.force_authenticate(user=None)
        self.client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        schema = RelationTypeVersion.objects.get(relation_type_id=APPLICATION_TYPE, version=1)
        url = reverse("admin:catalog_relationrecord_add") + f"?schema={schema.pk}"
        page = self.client.get(url)
        self.assertContains(page, "preparation")
        self.assertContains(page, "target")
        import json

        response = self.client.post(
            url,
            {
                "schema": schema.pk,
                "role_preparation": [
                    RelationEntityGrant.objects.get(grant=self.site_grant, entity=self.preparation).pk
                ],
                "role_crop": [self.crop.pk],
                "role_target": [RelationEntityGrant.objects.get(grant=self.site_grant, entity=self.target).pk],
                "payload": json.dumps(self.draft["payload"]),
                "source": json.dumps(self.draft["source"]),
            },
        )
        self.assertEqual(response.status_code, 302)
        record = RelationRecord.objects.get()
        self.assertContains(
            self.client.get(reverse("admin:catalog_relationrecord_change", args=[record.pk])), "synthetic-formulation-A"
        )

    def grant_global_actions(self):
        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="catalog", codename__in=["withdraw_relation", "reinstate_relation"]
            )
        )

    def test_non_object_preparation_provenance_returns_validation_without_partial_write(self):
        preparation = CatalogEntity.objects.create(
            kind="preparation", provenance=["legacy unverified source"], created_by=self.actor
        )
        RelationEntityGrant.objects.create(grant=self.site_grant, entity=preparation)
        self.draft["participants"]["preparation"] = [str(preparation.pk)]
        result = self.client.post(self.url, self.draft, format="json", headers={"idempotency-key": "legacy-provenance"})
        self.assertEqual(result.status_code, 400)
        self.assertEqual(result.data["error"]["code"], "validation_error")
        self.assertEqual(RelationRecord.objects.count(), 0)
        self.assertEqual(RelationRevision.objects.count(), 0)
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 0)
        self.assertEqual(ImportReceipt.objects.count(), 0)
        preparation.refresh_from_db()
        self.assertEqual(preparation.provenance, ["legacy unverified source"])

    def test_explicit_withdrawal_retry_and_fresh_reinstatement_keep_releases_disabled(self):
        record = self.approve(self.create().data["record"])
        response = self.action(
            "catalog-release", record, {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        )
        record = response.data["record"]
        url = reverse("catalog-withdraw", args=[record["id"]])
        body = {"reason": "Synthetic source contradiction", "evidence": {"decision": "synthetic reviewed withdrawal"}}
        headers = {"HTTP_IF_MATCH": record["etag"], "HTTP_IDEMPOTENCY_KEY": "withdraw-one"}
        self.assertEqual(self.client.post(url, body, format="json", **headers).status_code, 403)
        self.grant_global_actions()
        result = self.client.post(url, body, format="json", **headers)
        self.assertEqual(result.status_code, 200, result.data)
        withdrawn = result.data["record"]
        self.assertTrue(withdrawn["withdrawn"])
        self.assertFalse(withdrawn["release"]["enabled"])
        replay = self.client.post(url, body, format="json", **headers)
        self.assertEqual(replay.status_code, 200, replay.data)
        self.assertEqual(result.data["withdrawal_id"], replay.data["withdrawal_id"])
        self.assertEqual(RelationRecord.objects.get().eligibility_epoch, 1)
        self.assertEqual(RelationRecord.objects.get().withdrawals.count(), 1)
        stale = self.action(
            "catalog-release", withdrawn, {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        )
        self.assertEqual(stale.status_code, 409)
        self.draft["source"]["version"] = "2"
        self.draft["payload"]["checked_at"] = timezone.now().isoformat()
        updated = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            self.draft,
            format="json",
            headers={"if-match": withdrawn["etag"], "idempotency-key": "restoration-draft"},
        )
        self.assertEqual(updated.status_code, 201, updated.data)
        unapproved = self.action(
            "catalog-reinstate",
            updated.data["record"],
            {
                "revision_id": updated.data["record"]["latest_revision"]["id"],
                "withdrawal_id": result.data["withdrawal_id"],
                "evidence": {"resolution": "Unapproved draft must not restore eligibility"},
            },
        )
        self.assertEqual(unapproved.status_code, 409)
        self.assertEqual(unapproved.data["error"]["code"], "invalid_transition")
        current = RelationRecord.objects.get()
        self.assertTrue(current.withdrawn)
        self.assertFalse(current.releases.get().enabled)
        candidate = self.action("catalog-submit", updated.data["record"], revision=True).data["record"]
        reviewed = self.action(
            "catalog-review", candidate, {"action": "approve", "content_locale": "uk"}, revision=True
        )
        self.assertEqual(reviewed.status_code, 200, reviewed.data)
        candidate = reviewed.data["record"]
        data = {
            "revision_id": candidate["latest_revision"]["id"],
            "withdrawal_id": result.data["withdrawal_id"],
            "evidence": {"resolution": "Synthetic new evidence resolves the prior decision"},
        }
        restored = self.action("catalog-reinstate", candidate, data)
        self.assertEqual(restored.status_code, 200, restored.data)
        self.assertFalse(restored.data["record"]["withdrawn"])
        self.assertFalse(restored.data["record"]["release"]["enabled"])
        self.assertEqual(RelationAuditEvent.objects.filter(action="reinstate", actor=self.actor).count(), 1)

    def test_admin_global_action_exposes_decision_and_uses_shared_withdrawal_policy(self):
        record = self.approve(self.create().data["record"])
        self.grant_global_actions()
        self.client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        url = reverse("admin:catalog_relationrecord_change", args=[record["id"]])
        page = self.client.get(url)
        self.assertContains(page, "Withdraw globally")
        from uuid import uuid4

        result = self.client.post(
            url,
            {
                "action": "withdraw",
                "version": record["lock_version"],
                "reason": "Synthetic admin withdrawal",
                "evidence": '{"source": "synthetic-reviewed-decision"}',
                "operation_key": str(uuid4()),
            },
        )
        self.assertEqual(result.status_code, 302)
        page = self.client.get(url)
        self.assertContains(page, "Synthetic admin withdrawal")
        self.assertContains(page, "synthetic-reviewed-decision")
        self.assertTrue(RelationRecord.objects.get().withdrawn)


class ApplicationConcurrencyTests(CatalogFixtures, TransactionTestCase):
    participant = ApplicationTests.participant

    def setUp(self):
        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        ApplicationTests.setUp(self)

    def test_concurrent_application_create_has_one_typed_revision_and_receipt(self):
        module = import_module("api.v1.content.tests.test_catalog_relations")
        module.CatalogAPIConcurrentTests.test_two_connections_replay_one_atomic_create_and_receipt(self)
        self.assertEqual(PlantProtectionApplicationDetails.objects.count(), 1)
