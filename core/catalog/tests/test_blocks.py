import copy
import json

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse

from api.v1.content.tests import test_catalog_bulk as bulk_tests
from api.v1.content.tests.test_catalog_relations import CatalogFixtures
from core.catalog.access_models import RelationEntityGrant
from core.catalog.block_models import BlockConfigurationAudit, BlockConfigurationRevision
from core.catalog.blocks import BlockAccess, select_configured_blocks
from core.catalog.relation_service import RelationConflict
from core.catalog.tests import test_applications as app_tests
from core.classifier.models import CategoryHub
from core.posts.models import GuideSection, GuideSectionArticle
from core.utils.tests.factories import CategoryFactory


class BlockTests(CatalogFixtures, TestCase):
    setUp_application = app_tests.ApplicationTests.setUp
    participant = app_tests.ApplicationTests.participant
    grant_review = app_tests.ApplicationTests.grant_review
    grant_global_actions = app_tests.ApplicationTests.grant_global_actions
    approved_record = bulk_tests.ApplicationBulkTests.approved_record

    def setUp(self):
        self.setUp_application()
        self.hub = CategoryHub.objects.create(category=self.category, is_active=True, site=self.site, locale="uk")
        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=[
                    "view_blockconfiguration",
                    "add_blockconfiguration",
                    "change_blockconfiguration",
                    "publish_blockconfiguration",
                ],
            )
        )
        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="classifier",
                codename__in=["view_category", "view_categoryhub", "change_categoryhub"],
            )
        )
        self.access = BlockAccess(self.actor, self.site.pk)
        self.blocks = [
            {
                "version": 1,
                "slot": "crop.related_preparations",
                "title": "Synthetic preparations",
                "type": "plant_protection_application",
                "context_role": "crop",
                "result_role": "preparation",
                "filters": ["target", "method"],
                "conditions": {},
                "country_policy": "resolved_market",
                "sort": "canonical_title_uuid",
                "page_size": 12,
                "empty": "hide",
                "presentation": "catalog_cards",
                "manual_replacement": "none",
                "manual_ids": [],
            }
        ]
        self.blocks_url = reverse("content-hub-blocks", args=[self.hub.pk]) + "?content_locale=uk"

    def context(self, entity=None):
        from core.catalog.selection import resolve_catalog_context

        return resolve_catalog_context(
            site=self.site, content_locale="uk", country="UA", page_entity=entity or self.crop_entity.pk
        )

    def save(self):
        return self.access.save(self.hub.pk, "uk", self.blocks, None)

    def activate(self, config):
        revision = config.revisions.latest("number")
        plan = self.access.preview(self.hub.pk, "uk", revision.pk, "UA")
        return self.access.activate(self.hub.pk, "uk", config.lock_version, plan["preview"])

    def test_api_roundtrip_explicit_activation_history_and_off(self):
        self.approved_record()
        created = self.client.post(self.blocks_url, {"blocks": self.blocks}, format="json", HTTP_IF_NONE_MATCH="*")
        self.assertEqual(created.status_code, 201, created.data)
        current = created.data["configuration"]
        self.assertFalse(current["enabled"])
        self.assertEqual(select_configured_blocks(self.context(), self.hub.pk), [])

        def action(a):
            return reverse("content-hub-block-action", args=[self.hub.pk, a]) + "?content_locale=uk"

        preview = self.client.post(
            action("preview"), {"revision_id": current["revisions"][0]["id"], "country": "UA"}, format="json"
        )
        self.assertEqual(preview.status_code, 200, preview.data)
        published = self.client.post(
            action("activate"), {"preview": preview.data["preview"]}, format="json", HTTP_IF_MATCH=current["etag"]
        )
        self.assertEqual(published.status_code, 200, published.data)
        self.assertEqual(select_configured_blocks(self.context(), self.hub.pk)[0]["selection"]["count"], 1)
        live_id = published.data["configuration"]["active_revision_id"]
        self.blocks[0]["title"] = "Pending title"
        draft = self.client.post(
            self.blocks_url,
            {"blocks": self.blocks},
            format="json",
            HTTP_IF_MATCH=published.data["configuration"]["etag"],
        )
        self.assertEqual(draft.status_code, 201, draft.data)
        self.assertEqual(draft.data["configuration"]["active_revision_id"], live_id)
        self.assertEqual(select_configured_blocks(self.context(), self.hub.pk)[0]["title"], "Synthetic preparations")
        off = self.client.post(action("disable"), {}, format="json", HTTP_IF_MATCH=draft.data["configuration"]["etag"])
        self.assertEqual(off.status_code, 200, off.data)
        self.assertEqual(select_configured_blocks(self.context(), self.hub.pk), [])
        self.assertEqual(BlockConfigurationRevision.objects.count(), 2)
        self.assertEqual(BlockConfigurationAudit.objects.count(), 4)

    def test_invalid_schema_no_code_and_limits(self):
        for changes in (
            {"sql": "SELECT 1"},
            {"type": "exec"},
            {"filters": ["python"]},
            {"page_size": 21},
            {"page_size": True},
            {"empty": "manual_fallback"},
            {"presentation": "../../template"},
            {"context_role": "preparation"},
            {"conditions": {"target": ["invalid"]}},
            {"manual_ids": [True]},
        ):
            blocks = copy.deepcopy(self.blocks)
            blocks[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.access.save(self.hub.pk, "uk", blocks, None)
        with self.assertRaises(ValidationError):
            self.access.save(self.hub.pk, "uk", self.blocks * 4, None)
        self.assertEqual(BlockConfigurationRevision.objects.count(), 0)

    def test_order_empty_second_crop_and_site_owner_binding(self):
        self.blocks += [
            {**self.blocks[0], "slot": "crop.related_problems", "title": "Problems", "result_role": "target"}
        ]
        config = self.save()
        preview = self.access.preview(self.hub.pk, "uk", config.revisions.get().pk, "UA")
        self.assertEqual([b["title"] for b in preview["blocks"]], ["Synthetic preparations", "Problems"])
        self.activate(config)
        self.assertTrue(all(not b["visible"] for b in select_configured_blocks(self.context(), self.hub.pk)))
        crop2 = self.participant("crop", "Second crop")
        category2 = CategoryFactory(parent=self.root, entity=crop2)
        hub2 = CategoryHub.objects.create(category=category2, is_active=True, site=self.site, locale="uk")
        cfg2 = self.access.save(hub2.pk, "uk", self.blocks, None)
        self.assertEqual(cfg2.owner_id, crop2.pk)
        self.assertEqual(select_configured_blocks(self.context(crop2.pk), self.hub.pk), [])
        with self.assertRaises(Exception) as denied:
            BlockAccess(self.actor, self.other_site.pk).read(self.hub.pk, "uk")
        self.assertIn(type(denied.exception).__name__, ["PermissionDenied", "Http404"])

    def test_stale_preview_versions_permission_and_participant_revocation(self):
        self.approved_record()
        config = self.save()
        revision = config.revisions.get()
        preview = self.access.preview(self.hub.pk, "uk", revision.pk, "UA")
        self.site_grant.can_publish = False
        self.site_grant.save()
        with self.assertRaises(PermissionDenied):
            self.access.activate(self.hub.pk, "uk", config.lock_version, preview["preview"])
        self.site_grant.can_publish = True
        self.site_grant.save()
        self.blocks[0]["title"] = "New draft"
        self.access.save(self.hub.pk, "uk", self.blocks, config.lock_version)
        with self.assertRaises(RelationConflict):
            self.access.activate(self.hub.pk, "uk", config.lock_version, preview["preview"])
        self.blocks[0]["conditions"] = {"target": [str(self.target.pk)]}
        config.refresh_from_db()
        updated = self.access.save(self.hub.pk, "uk", self.blocks, config.lock_version)
        RelationEntityGrant.objects.filter(grant=self.site_grant, entity=self.target).delete()
        with self.assertRaises(PermissionDenied):
            self.access.read(self.hub.pk, "uk")
        self.assertFalse(updated.enabled)

    def test_manual_manifest_preserves_existing_guide_and_market(self):
        section = GuideSection.objects.create(category=self.category, title="Guide")
        placement = GuideSectionArticle.objects.create(section=section, post=self.post)
        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="posts",
                codename__in=["view_post", "view_guidesection", "view_guidesectionarticle"],
            )
        )
        self.blocks[0].update(manual_replacement="guide_placements", manual_ids=[placement.pk])
        config = self.save()
        preview = self.access.preview(self.hub.pk, "uk", config.revisions.get().pk, "UA")
        self.assertEqual(preview["manual_manifest"][0]["id"], placement.pk)
        self.activate(config)
        self.assertTrue(GuideSectionArticle.objects.filter(pk=placement.pk, post=self.post).exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            placement.delete()
        self.hub.refresh_from_db()
        self.assertIsNone(self.hub.market_category_id)

    def test_immutable_revisions_and_admin_roundtrip(self):
        config = self.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            config.revisions.update(blocks=[])
        admin_client = Client()
        admin_client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        url = reverse("admin:classifier_categoryhub_catalog_blocks", args=[self.hub.pk]) + "?content_locale=uk"
        page = admin_client.get(url)
        self.assertContains(page, "Save draft revision")
        self.blocks[0]["title"] = "Admin revision"
        response = admin_client.post(
            url, {"action": "save", "version": config.lock_version, "blocks": json.dumps(self.blocks)}
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(config.revisions.count(), 2)

    def test_api_permissions_preconditions_malformed_and_unknown_scope(self):
        response = self.client.post(self.blocks_url, {"blocks": self.blocks}, format="json")
        self.assertEqual(response.status_code, 428, response.data)
        response = self.client.post(
            self.blocks_url, {"blocks": self.blocks, "sql": "x"}, format="json", HTTP_IF_NONE_MATCH="*"
        )
        self.assertEqual(response.status_code, 400, response.data)
        config = self.save()
        response = self.client.post(self.blocks_url, {"blocks": self.blocks}, format="json", HTTP_IF_MATCH='"bad:1"')
        self.assertEqual(response.status_code, 409)
        denied = self.client.get(self.blocks_url + "&extra=1")
        self.assertEqual(denied.status_code, 400)
        self.actor.user_permissions.remove(
            Permission.objects.get(content_type__app_label="catalog", codename="view_blockconfiguration")
        )
        denied = self.client.get(self.blocks_url)
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(config.revisions.count(), 1)

    def test_preview_expires_and_visibility_change_requires_new_review(self):
        from django.test import override_settings

        from core.posts.models import Post

        self.approved_record()
        config = self.save()
        preview = self.access.preview(self.hub.pk, "uk", config.revisions.get().pk, "UA")
        with override_settings(CATALOG_BLOCK_PREVIEW_MAX_AGE=-1), self.assertRaises(RelationConflict):
            self.access.activate(self.hub.pk, "uk", config.lock_version, preview["preview"])
        Post.objects.filter(entity=self.target).update(status=False)
        with self.assertRaises(RelationConflict):
            self.access.activate(self.hub.pk, "uk", config.lock_version, preview["preview"])
        config.refresh_from_db()
        self.assertFalse(config.enabled)
        self.assertEqual(config.lock_version, 2)

    def test_admin_csrf_preview_activate_disable_and_language_picker(self):
        self.approved_record()
        config = self.save()
        admin_client = Client(enforce_csrf_checks=True)
        admin_client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        path = reverse("admin:classifier_categoryhub_catalog_blocks", args=[self.hub.pk])
        self.assertContains(admin_client.get(path), "Choose content language")
        url = path + "?content_locale=uk"
        self.assertContains(admin_client.get(url), "Preview public cards")
        data = {"action": "preview", "revision_id": config.revisions.get().pk, "country": "UA"}
        self.assertEqual(admin_client.post(url, data).status_code, 403)
        data["csrfmiddlewaretoken"] = admin_client.cookies["csrftoken"].value
        preview = admin_client.post(url, data)
        self.assertContains(preview, "Activate reviewed configuration")
        plan = preview.context_data["plan"]
        activated = admin_client.post(
            url,
            {
                "action": "activate",
                "version": config.lock_version,
                "preview": plan["preview"],
                "csrfmiddlewaretoken": admin_client.cookies["csrftoken"].value,
            },
        )
        self.assertEqual(activated.status_code, 302)
        config.refresh_from_db()
        self.assertTrue(config.enabled)
        self.assertEqual(select_configured_blocks(self.context(), self.hub.pk)[0]["selection"]["count"], 1)

    def test_public_budget_three_blocks_and_fixed_filters_cannot_broaden(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.approved_record()
        self.blocks[0]["conditions"] = {"target": [str(self.target.pk)]}
        self.blocks += [
            {**self.blocks[0], "slot": "crop.related_problems", "title": "Problems", "result_role": "target"},
            {
                **self.blocks[0],
                "slot": "crop.related_catalog",
                "type": "cultivar_of",
                "result_role": "cultivar",
                "title": "Cultivars",
                "filters": [],
                "conditions": {},
            },
        ]
        config = self.save()
        self.activate(config)
        with CaptureQueriesContext(connection) as queries:
            result = select_configured_blocks(self.context(), self.hub.pk)
        self.assertEqual(len(queries), 7)
        self.assertEqual([b["title"] for b in result if b["visible"]], ["Synthetic preparations", "Problems"])
        other = self.participant("disease", "Other target")
        with self.assertRaises(ValidationError):
            select_configured_blocks(
                self.context(), self.hub.pk, filters={self.blocks[0]["slot"]: {"target": [str(other.pk)]}}
            )

    def test_off_on_does_not_restore_withdrawn_application_or_source(self):
        from core.catalog.relation_access import RelationAccess
        from core.catalog.relations import RelationRecord

        record = self.approved_record()
        config = self.activate(self.save())
        self.grant_global_actions()
        RelationAccess(type(self.actor).objects.get(pk=self.actor.pk), self.site.pk).withdraw_application(
            record_id=record["id"],
            expected_version=record["lock_version"],
            reason="synthetic",
            evidence={"review": "synthetic"},
            operation_key="block-withdraw",
        )
        config = self.access.disable(self.hub.pk, "uk", config.lock_version)
        config = self.activate(config)
        self.assertTrue(config.enabled)
        self.assertTrue(all(not b["visible"] for b in select_configured_blocks(self.context(), self.hub.pk)))
        row = RelationRecord.objects.get(pk=record["id"])
        self.assertEqual(row.eligibility_epoch, 1)
        self.assertTrue(row.withdrawn)
        self.assertFalse(row.releases.get().enabled)

    def test_database_rejects_foreign_pointer_scope_mutation_and_null_schema(self):
        config = self.save()
        for update in ({"content_locale": "en", "lock_version": 3}, {"lock_version": 1}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                type(config).objects.filter(pk=config.pk).update(**update)
        with self.assertRaises(IntegrityError), transaction.atomic():
            BlockConfigurationRevision.objects.create(
                configuration=config, number=2, blocks=[{**self.blocks[0], "presentation": None}], created_by=self.actor
            )


class BlockConcurrencyTests(CatalogFixtures, TransactionTestCase):
    def setUp(self):
        from importlib import import_module
        from types import SimpleNamespace

        from django.apps import apps
        from django.db import connection

        import_module("core.catalog.migrations.0005_relation_definitions").bootstrap(
            apps, SimpleNamespace(connection=connection)
        )
        BlockTests.setUp(self)

    setUp_application = app_tests.ApplicationTests.setUp
    participant = app_tests.ApplicationTests.participant
    save = BlockTests.save

    def test_two_connections_cannot_lose_a_revision_update(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connection

        config = self.save()
        barrier = Barrier(2)

        def worker(title):
            close_old_connections()
            try:
                actor = type(self.actor).objects.get(pk=self.actor.pk)
                blocks = copy.deepcopy(self.blocks)
                blocks[0]["title"] = title
                barrier.wait(timeout=5)
                try:
                    BlockAccess(actor, self.site.pk).save(self.hub.pk, "uk", blocks, config.lock_version)
                    return "saved"
                except RelationConflict:
                    return "conflict"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(worker, ["Concurrent A", "Concurrent B"]))
        self.assertCountEqual(outcomes, ["saved", "conflict"])
        self.assertEqual(config.revisions.count(), 2)

    def test_concurrent_guide_delete_and_new_binding_returns_conflict(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from unittest.mock import patch

        from django.db import close_old_connections, connection
        from django.db.models.deletion import Collector
        from django.http import HttpResponse
        from rest_framework.test import APIClient

        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="posts",
                codename__in=[
                    "view_post",
                    "view_guidesection",
                    "view_guidesectionarticle",
                    "delete_guidesection",
                    "delete_guidesectionarticle",
                ],
            )
        )
        section = GuideSection.objects.create(category=self.category, title="race")
        placement = GuideSectionArticle.objects.create(section=section, post=self.post)
        collected, bound = Event(), Event()
        original_delete = Collector.delete

        def paused_delete(collector, *args, **kwargs):
            if GuideSection in collector.data:
                collected.set()
                if not bound.wait(10):
                    raise AssertionError("binding did not finish")
            return original_delete(collector, *args, **kwargs)

        def deletion():
            close_old_connections()
            try:
                client = APIClient(raise_request_exception=False)
                client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
                return client.delete(reverse("content-guide-section-detail", args=[section.pk])).status_code
            finally:
                connection.close()

        with patch.object(Collector, "delete", paused_delete), patch(
            "django.core.handlers.exception.handle_uncaught_exception", return_value=HttpResponse(status=500)
        ), ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(deletion)
            self.assertTrue(collected.wait(10), "delete did not collect")
            try:
                self.blocks[0].update(manual_replacement="guide_placements", manual_ids=[placement.pk])
                self.access = BlockAccess(type(self.actor).objects.get(pk=self.actor.pk), self.site.pk)
                config = self.access.save(self.hub.pk, "uk", self.blocks, None)
                self.assertEqual(config.revisions.count(), 1)
            finally:
                bound.set()
            status = future.result(timeout=15)
        self.assertTrue(GuideSectionArticle.objects.filter(pk=placement.pk).exists())
        self.assertEqual(status, 409, "Concurrent newly protected Guide deletion must return controlled conflict")
