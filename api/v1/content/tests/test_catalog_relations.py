import copy
import json
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

from django.apps import apps
from django.contrib.auth.models import Permission
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.models import CatalogEntity
from core.catalog.relations import ImportReceipt, RelationAuditEvent, RelationRecord
from core.catalog.tests import test_relation_admin


class CatalogFixtures:
    editor = staticmethod(test_relation_admin.RelationAdminTests.editor)
    publication_fixture = test_relation_admin.RelationAdminTests.publication_fixture
    publication_rights = test_relation_admin.RelationAdminTests.publication_rights

    def setup_catalog(self):
        test_relation_admin.RelationAdminTests.setUp(self)
        self.client = APIClient()
        self.token = Token.objects.create(user=self.actor)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.url = reverse("catalog-relations")
        self.draft = {
            "type_code": "cultivar_of",
            "schema_version": 1,
            "participants": {"crop": [str(self.crop_entity.pk)], "cultivar": [str(self.cultivar_entity.pk)]},
            "payload": {"note": "version one"},
            "source": {"citation": "synthetic source"},
        }

    def create(self, key="create-one"):
        result = self.client.post(self.url, self.draft, format="json", headers={"idempotency-key": key})
        self.assertEqual(result.status_code, 201, result.data)
        return result

    def action(self, name, record, body=None, tag=None, revision=False):
        pk = record["latest_revision"]["id"] if revision else record["id"]
        return self.client.post(
            reverse(name, args=[pk]), body or {}, format="json", headers={"if-match": tag or record["etag"]}
        )


class CatalogAPITests(CatalogFixtures, TestCase):
    def setUp(self):
        self.setup_catalog()

    def test_discovery_search_and_bounded_cursor_pages(self):
        for name in ("catalog-entity-types", "catalog-relation-types", "catalog-entities"):
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["version"], 1)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertIn("noindex", response["X-Robots-Tag"])
        schemas = self.client.get(reverse("catalog-relation-types")).data["results"]
        self.assertTrue({"related_to", "cultivar_of"}.issubset({item["type_code"] for item in schemas}))
        entities = reverse("catalog-entities")
        page = self.client.get(entities, {"page_size": 1})
        next_page = self.client.get(page.data["next"])
        self.assertNotEqual(page.data["results"][0]["id"], next_page.data["results"][0]["id"])
        self.assertIsNone(next_page.data["next"])
        for params in ({"q": "Fixture cultivar"}, {"kind": "cultivar"}, {"schema": self.schema.pk, "role": "cultivar"}):
            found = self.client.get(entities, params)
            self.assertEqual([row["id"] for row in found.data["results"]], [str(self.cultivar_entity.pk)])
        found = self.client.get(entities, {"category": self.category.pk})
        self.assertEqual(len(found.data["results"]), 2)
        for params in (
            {"kind": "invalid"},
            {"category": "x"},
            {"schema": "x", "role": "crop"},
            {"role": "missing"},
            {"page_size": 51},
            {"extra": 1},
        ):
            response = self.client.get(entities, params)
            self.assertEqual(response.status_code, 400, response.data)

    def test_full_lifecycle_and_audit_actor(self):
        self.publication_fixture()
        self.publication_rights(review=True, publish=True)
        created = self.create()
        record = created.data["record"]
        detail_url = reverse("catalog-relation", args=[record["id"]])
        read = self.client.get(detail_url)
        self.assertEqual(read["ETag"], created["ETag"])
        edited = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            {**self.draft, "payload": {"note": "version two"}},
            format="json",
            headers={"if-match": read["ETag"], "idempotency-key": "edit-two"},
        )
        self.assertEqual(edited.status_code, 201, edited.data)
        record = edited.data["record"]
        submitted = self.action("catalog-submit", record, revision=True)
        self.assertEqual(submitted.status_code, 200, submitted.data)
        record = submitted.data["record"]
        approved = self.action("catalog-review", record, {"action": "approve", "content_locale": "uk"}, revision=True)
        self.assertEqual(approved.status_code, 200, approved.data)
        record = approved.data["record"]
        published = self.action(
            "catalog-release", record, {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        )
        self.assertEqual(published.status_code, 200, published.data)
        self.assertTrue(published.data["record"]["release"]["enabled"])
        record = published.data["record"]
        # A newer draft leaves the release pointer intact. Unrelease targets that pointer.
        draft = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            self.draft,
            format="json",
            headers={"if-match": published["ETag"], "idempotency-key": "new-draft"},
        )
        self.assertEqual(draft.status_code, 201, draft.data)
        record = draft.data["record"]
        self.assertNotEqual(record["latest_revision"]["id"], record["release"]["approved_revision_id"])
        hidden = self.action("catalog-unrelease", record)
        self.assertEqual(hidden.status_code, 200, hidden.data)
        self.assertFalse(hidden.data["record"]["release"]["enabled"])
        archived = self.client.delete(detail_url, {}, format="json", headers={"if-match": hidden["ETag"]})
        self.assertEqual(archived.status_code, 200, archived.data)
        self.assertTrue(archived.data["record"]["archived"])
        revisions = self.client.get(reverse("catalog-revisions", args=[record["id"]]), {"page_size": 1})
        self.assertIsNotNone(revisions.data["next"])
        audit = self.client.get(reverse("catalog-audit", args=[record["id"]]))
        self.assertTrue(all(row["actor"] == self.actor.pk for row in audit.data["results"]))
        self.assertIn("archive", [row["action"] for row in audit.data["results"]])

    def test_create_retry_receipt_and_conflicts_are_atomic(self):
        first = self.create()
        replay = self.create()
        self.assertEqual(first.data, replay.data)
        self.assertEqual(replay["Idempotent-Replay"], "true")
        self.assertEqual(RelationRecord.objects.count(), 1)
        self.assertEqual(RelationAuditEvent.objects.count(), 1)
        receipt = self.client.get(reverse("catalog-operation", args=["create-one"]))
        self.assertEqual(receipt.data, first.data)
        conflict = self.client.post(
            self.url,
            {**self.draft, "payload": {"different": True}},
            format="json",
            headers={"idempotency-key": "create-one"},
        )
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.data["error"]["code"], "idempotency_conflict")
        duplicate = self.client.post(self.url, self.draft, format="json", headers={"idempotency-key": "different-key"})
        self.assertEqual(duplicate.status_code, 409, duplicate.data)
        self.assertEqual(ImportReceipt.objects.count(), 1)
        missing = self.client.post(self.url, self.draft, format="json")
        self.assertEqual(missing.status_code, 400)

    def test_revision_replay_precedes_stale_check_but_new_key_cannot_overwrite(self):
        record = self.create().data["record"]
        url = reverse("catalog-revisions", args=[record["id"]])
        headers = {"HTTP_IF_MATCH": record["etag"], "HTTP_IDEMPOTENCY_KEY": "edit"}
        first = self.client.post(url, self.draft, format="json", **headers)
        second = self.client.post(url, self.draft, format="json", **headers)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data, second.data)
        missing = self.client.post(url, self.draft, format="json", headers={"idempotency-key": "no-precondition"})
        self.assertEqual(missing.status_code, 428)
        stale = self.client.post(
            url, self.draft, format="json", headers={"if-match": record["etag"], "idempotency-key": "stale"}
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.data["error"]["code"], "stale_version")
        self.assertEqual(RelationRecord.objects.get().revisions.count(), 2)

    def test_permission_matrix_and_revoked_receipt_access(self):
        self.client.credentials()
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Token invalid")
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.actor.is_staff = False
        self.actor.save(update_fields=["is_staff"])
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.actor.is_staff = True
        self.actor.save(update_fields=["is_staff"])
        self.actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label="catalog", codename="view_relationrecord")
        )
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.actor.user_permissions.add(
            Permission.objects.get(content_type__app_label="catalog", codename="view_relationrecord")
        )
        created = self.create()
        self.site_grant.can_edit = False
        self.site_grant.save(update_fields=["can_edit"])
        self.assertEqual(
            self.client.post(
                self.url, self.draft, format="json", headers={"idempotency-key": "create-one"}
            ).status_code,
            403,
        )
        self.cultivar.delete()
        self.assertEqual(
            self.client.get(reverse("catalog-relation", args=[created.data["record"]["id"]])).status_code, 404
        )
        self.assertEqual(self.client.get(reverse("catalog-operation", args=["create-one"])).status_code, 404)
        self.assertEqual(self.client.get(self.url).data["results"], [])

    def test_foreign_site_and_direct_revision_ids_are_hidden(self):
        created = self.create().data["record"]
        RelationSiteGrant.objects.create(actor=self.actor, site=self.other_site, can_edit=True)
        with self.settings.__class__(SITE_ID=self.other_site.pk):
            self.assertEqual(self.client.get(self.url).data["results"], [])
            for name, pk in (
                ("catalog-relation", created["id"]),
                ("catalog-revisions", created["id"]),
                ("catalog-audit", created["id"]),
            ):
                self.assertEqual(self.client.get(reverse(name, args=[pk])).status_code, 404)
            response = self.action("catalog-submit", created, revision=True)
            self.assertEqual(response.status_code, 404)
        self.assertEqual(self.client.get(reverse("catalog-relation", args=[uuid4()])).status_code, 404)
        invalid = self.client.get(reverse("catalog-relation", args=["invalid"]))
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.data["error"]["code"], "validation_error")

    def test_strict_schema_and_lifecycle_payloads_fail_without_writes(self):
        for changes in (
            {"state": "approved"},
            {"site_id": self.other_site.pk},
            {"type_code": "missing"},
            {"schema_version": 999},
            {"participants": {"unknown": [str(self.crop_entity.pk)]}},
            {"participants": {"crop": ["invalid"]}},
            {"payload": []},
            {"participants": {"crop": [str(self.cultivar_entity.pk)], "cultivar": [str(self.crop_entity.pk)]}},
        ):
            result = self.client.post(
                self.url, {**self.draft, **changes}, format="json", headers={"idempotency-key": "invalid"}
            )
            self.assertEqual(result.status_code, 400, result.data)
            self.assertEqual(ImportReceipt.objects.count(), 0)
            self.assertEqual(RelationRecord.objects.count(), 0)
        record = self.create().data["record"]
        result = self.action("catalog-submit", record, {"reviewed_by": self.actor.pk}, revision=True)
        self.assertEqual(result.status_code, 400)
        self.assertEqual(RelationRecord.objects.get().revisions.get().state, "draft")
        changed_type = self.client.post(
            reverse("catalog-revisions", args=[record["id"]]),
            {**self.draft, "type_code": "related_to"},
            format="json",
            headers={"if-match": record["etag"], "idempotency-key": "change-type"},
        )
        self.assertEqual(changed_type.status_code, 400)  # roles do not fit the other schema

    def test_review_publish_capabilities_and_current_material_gate(self):
        self.publication_fixture()
        record = self.create().data["record"]
        submitted = self.action("catalog-submit", record, revision=True).data["record"]
        review_body = {"action": "approve", "content_locale": "uk"}
        self.assertEqual(self.action("catalog-review", submitted, review_body, revision=True).status_code, 403)
        self.publication_rights(review=True)
        approved = self.action("catalog-review", submitted, review_body, revision=True)
        self.assertEqual(approved.status_code, 200, approved.data)
        record = approved.data["record"]
        body = {"revision_id": record["latest_revision"]["id"], "content_locale": "uk"}
        self.assertEqual(self.action("catalog-release", record, body).status_code, 403)
        self.publication_rights(review=True, publish=True)
        self.assertEqual(self.action("catalog-release", record, {**body, "content_locale": "en"}).status_code, 400)
        self.post.text += " changed after approval"
        self.post.save(update_fields=["text"])
        self.assertEqual(self.action("catalog-release", record, body).status_code, 400)
        self.assertFalse(RelationRecord.objects.get().releases.exists())

    def test_reverse_roles_and_relation_pagination(self):
        self.create()
        other = CatalogEntity.objects.create(kind="crop", provenance={"fixture": True}, created_by=self.actor)
        RelationEntityGrant.objects.create(grant=self.site_grant, entity=other)
        for entity in (self.crop_entity, self.cultivar_entity):
            draft = {
                "type_code": "related_to",
                "schema_version": 1,
                "participants": {"member": [str(other.pk), str(entity.pk)]},
            }
            response = self.client.post(self.url, draft, format="json", headers={"idempotency-key": str(entity.pk)})
            self.assertEqual(response.status_code, 201, response.data)
        first = self.client.get(self.url, {"page_size": 1})
        seen = []
        while True:
            seen.extend(row["id"] for row in first.data["results"])
            if not first.data["next"]:
                break
            first = self.client.get(first.data["next"])
        self.assertEqual(len(set(seen)), 3)
        direct = self.client.get(self.url, {"entity": self.crop_entity.pk, "role": "crop"})
        self.assertEqual(len(direct.data["results"]), 1)
        reverse = self.client.get(self.url, {"entity": self.cultivar_entity.pk, "role": "cultivar"})
        self.assertEqual(len(reverse.data["results"]), 1)
        for params in (
            {"entity": "invalid"},
            {"entity": other.pk, "role": "invalid"},
            {"role": "member"},
            {"unknown": "x"},
        ):
            self.assertEqual(self.client.get(self.url, params).status_code, 400)

    def test_oversized_pagination_returns_controlled_validation_error(self):
        for name in ("catalog-entities", "catalog-relation-types", "catalog-relations"):
            response = self.client.get(reverse(name), {"page_size": "9" * 5000})
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["error"]["code"], "validation_error")
        self.assertEqual(RelationRecord.objects.count(), 0)

    def test_unrepresentable_json_text_is_rejected_before_any_write(self):
        for field in ("payload", "source"):
            for value in ({"note": "bad\x00text"}, {"nested": [{"bad\x00key": "value"}]}, {"note": "bad\ud800text"}):
                response = self.client.post(
                    self.url,
                    json.dumps({**self.draft, field: value}),
                    content_type="application/json",
                    headers={"idempotency-key": "bad-text"},
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.data["error"]["code"], "validation_error")
                self.assertEqual(RelationRecord.objects.count(), 0)
                self.assertEqual(ImportReceipt.objects.count(), 0)
                self.assertEqual(RelationAuditEvent.objects.count(), 0)
        # Literal escape text, emoji and normal Unicode remain valid stored content.
        self.draft["payload"] = {"note": "literal \\u0000 and 🌱"}
        created = self.create()
        self.assertEqual(created.data["record"]["latest_revision"]["payload"], self.draft["payload"])

    def test_unrepresentable_search_and_operation_text_returns_validation_error(self):
        for name, params in (
            ("catalog-entities", {"q": "bad\x00text"}),
            ("catalog-relations", {"type_code": "bad\x00text"}),
        ):
            response = self.client.get(reverse(name), params)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.data["error"]["code"], "validation_error")
        response = self.client.get(reverse("catalog-operation", args=["bad\x00key"]))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"]["code"], "validation_error")


class CatalogAPIConcurrentTests(CatalogFixtures, TransactionTestCase):
    def setUp(self):
        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        self.setup_catalog()

    def test_two_connections_replay_one_atomic_create_and_receipt(self):
        barrier = Barrier(2)
        draft, url, token = copy.deepcopy(self.draft), self.url, self.token.key

        def create():
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f"Token {token}")
                barrier.wait(timeout=10)
                result = client.post(url, draft, format="json", HTTP_IDEMPOTENCY_KEY="concurrent")
                return result.status_code, result.data
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: create(), range(2)))
        self.assertEqual([status for status, _ in results], [201, 201], results)
        self.assertEqual(results[0][1], results[1][1])
        self.assertEqual(RelationRecord.objects.count(), 1)
        self.assertEqual(ImportReceipt.objects.count(), 1)
        self.assertEqual(RelationAuditEvent.objects.count(), 1)
