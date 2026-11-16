from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.models import CatalogEntity
from core.catalog.relations import (
    EntityPresentationSelection,
    RelationAuditEvent,
    RelationRecord,
    RelationRelease,
    RelationTypeVersion,
    ReviewState,
)
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class RelationAdminTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="admin-a.example.test", name="A")
        self.other_site = Site.objects.create(domain="admin-b.example.test", name="B")
        self.settings = override_settings(SITE_ID=self.site.pk)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.actor = self.editor()
        self.site_grant = RelationSiteGrant.objects.create(actor=self.actor, site=self.site, can_edit=True)
        self.crop_entity = CatalogEntity.objects.create(
            kind="crop", provenance={"fixture": True}, created_by=self.actor
        )
        self.cultivar_entity = CatalogEntity.objects.create(
            kind="cultivar", provenance={"fixture": True}, created_by=self.actor
        )
        self.root = CategoryFactory()
        self.category = CategoryFactory(parent=self.root, value="Fixture crop", entity=self.crop_entity)
        self.post = PostFactory(title="Fixture cultivar", entity=self.cultivar_entity, rubric=self.category)
        self.crop = RelationEntityGrant.objects.create(
            grant=self.site_grant, entity=self.crop_entity, category=self.category
        )
        self.cultivar = RelationEntityGrant.objects.create(
            grant=self.site_grant, entity=self.cultivar_entity, post=self.post
        )
        self.schema = RelationTypeVersion.objects.get(relation_type_id="cultivar_of", version=1)
        self.add_url = reverse("admin:catalog_relationrecord_add") + f"?schema={self.schema.pk}"
        self.client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")

    @staticmethod
    def editor():
        actor = StaffUserFactory()
        actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=["view_relationrecord", "add_relationrecord", "change_relationrecord"],
            )
        )
        return actor

    def draft_form(self, **changes):
        return {"schema": self.schema.pk, "role_crop": [self.crop.pk], "role_cultivar": [self.cultivar.pk], **changes}

    def create_draft(self):
        result = self.client.post(self.add_url, self.draft_form())
        self.assertEqual(result.status_code, 302)
        return RelationRecord.objects.get()

    def test_schema_driven_draft_edit_submit_archive_and_reverse_view(self):
        form_page = self.client.get(self.add_url)
        self.assertContains(form_page, "Search participants")
        self.assertContains(form_page, "autocomplete")
        record = self.create_draft()
        record_url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        self.assertContains(self.client.get(record_url), "Revision history")
        first_version = record.lock_version
        edit = self.client.post(record_url, self.draft_form(version=first_version, payload='{"test": true}'))
        self.assertEqual(edit.status_code, 302)
        self.assertEqual(record.revisions.count(), 2)
        stale = self.client.post(record_url, self.draft_form(version=first_version))
        self.assertContains(stale, "Record version changed")
        self.assertEqual(record.revisions.count(), 2)
        record.refresh_from_db()
        invalid = self.client.post(record_url, {"action": "publish", "version": record.lock_version})
        self.assertEqual(invalid.context["action"].errors.as_data()["action"][0].code, "invalid_choice")
        self.assertFalse(RelationRelease.objects.exists())
        self.assertEqual(
            self.client.post(record_url, {"action": "submit", "version": record.lock_version}).status_code, 302
        )
        self.assertEqual(record.revisions.order_by("-number").first().state, ReviewState.SUBMITTED)
        record.refresh_from_db()
        self.assertEqual(
            self.client.post(record_url, {"action": "archive", "version": record.lock_version}).status_code, 302
        )
        record.refresh_from_db()
        self.assertTrue(record.archived)
        reverse_url = reverse("admin:catalog_relation_participant", args=[self.crop_entity.pk])
        self.assertContains(self.client.get(reverse_url), str(record.pk))
        self.assertContains(self.client.get(record_url), "Audit history")
        self.assertEqual(RelationAuditEvent.objects.get(action="archive").actor, self.actor)

    def test_autocomplete_role_filters_and_denies_foreign_grant_ids(self):
        url = reverse("admin:catalog_relation_autocomplete", args=[self.schema.pk, "crop"])
        data = self.client.get(url, {"q": "Fixture", "kind": "crop", "category": self.category.pk})
        self.assertEqual(data.status_code, 200)
        self.assertIn("no-store", data.headers["Cache-Control"])
        self.assertEqual([v["id"] for v in data.json()["results"]], [self.crop.pk])
        foreign = RelationSiteGrant.objects.create(actor=self.actor, site=self.other_site, can_edit=True)
        foreign_grant = RelationEntityGrant.objects.create(grant=foreign, entity=self.crop_entity)
        for value in (foreign_grant.pk, self.cultivar.pk):
            response = self.client.post(self.add_url, self.draft_form(role_crop=[value]))
            self.assertEqual(response.context["form"].errors.as_data()["role_crop"][0].code, "invalid_choice")
        self.assertFalse(RelationRecord.objects.exists())

    def test_direct_urls_and_post_are_denied_for_other_site_and_read_only(self):
        record = self.create_draft()
        record_url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        outsider = self.editor()
        other = RelationSiteGrant.objects.create(actor=outsider, site=self.other_site, can_edit=True)
        RelationEntityGrant.objects.create(grant=other, entity=self.crop_entity)
        RelationEntityGrant.objects.create(grant=other, entity=self.cultivar_entity)
        self.client.force_login(outsider, backend="core.pro_auth.backends.AuthBackend")
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(self.client.get(record_url).status_code, 404)
        self.assertEqual(
            self.client.post(record_url, {"action": "archive", "version": record.lock_version}).status_code, 404
        )
        self.site_grant.can_edit = False
        self.site_grant.save(update_fields=["can_edit"])
        self.client.force_login(self.actor, backend="core.pro_auth.backends.AuthBackend")
        self.assertContains(self.client.get(record_url), "Revision history")
        self.assertEqual(self.client.post(record_url, self.draft_form(version=record.lock_version)).status_code, 403)
        self.assertEqual(record.revisions.count(), 1)

    def publication_fixture(self):
        self.post.get_absolute_url()
        self.post.refresh_from_db()
        SiteContentPolicy.objects.create(site=self.site, active=True, content_locales=["uk"])
        for category in (self.root, self.category):
            SiteCategoryConfiguration.objects.create(
                site=self.site,
                category=category,
                content_locale="uk",
                visible=True,
                canonical_path=f"/category-{category.pk}/",
            )
        approval = PostPublicationApproval.objects.create(
            post=self.post,
            content_digest=material_digest(self.post),
            content_locale="uk",
            reviewed_by=self.actor,
            reviewed_at=timezone.now(),
            language_verified=True,
            provenance={"fixture": True},
        )
        SitePostPublication.objects.create(
            site=self.site,
            post=self.post,
            approval=approval,
            content_locale="uk",
            category=self.category,
            canonical_path=self.post.absolute_url,
            enabled=True,
            publish_at=timezone.now(),
        )
        for entity, anchor in (
            (self.crop_entity, {"category": self.category}),
            (self.cultivar_entity, {"post": self.post}),
        ):
            EntityPresentationSelection.objects.create(
                site=self.site,
                entity=entity,
                content_locale="uk",
                approved=True,
                updated_by=self.actor,
                **anchor,
            )

    def publication_rights(self, *, review=False, publish=False):
        self.site_grant.can_review = review
        self.site_grant.can_publish = publish
        self.site_grant.save(update_fields=["can_review", "can_publish"])
        codes = []
        if review:
            codes.append("review_relationrecord")
        if publish:
            codes.append("publish_relationrecord")
        self.actor.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="catalog", codename__in=codes)
        )

    def test_create_edit_review_publish_unpublish_archive_cycle(self):
        self.publication_fixture()
        self.publication_rights(review=True, publish=True)
        record = self.create_draft()
        url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        for action in ("submit", "approve", "publish"):
            record.refresh_from_db()
            response = self.client.post(url, {"action": action, "version": record.lock_version, "content_locale": "uk"})
            self.assertEqual(response.status_code, 302, str(response.context and response.context.get("action")))
        release = RelationRelease.objects.get(record=record)
        self.assertTrue(release.enabled)
        self.assertContains(self.client.get(url), "Published revision 1")
        record.refresh_from_db()
        self.assertEqual(self.client.post(url, self.draft_form(version=record.lock_version)).status_code, 302)
        release.refresh_from_db()
        self.assertEqual(release.approved_revision.number, 1)
        record.refresh_from_db()
        # Unpublish targets the current live pointer even when the latest is a draft.
        self.assertEqual(
            self.client.post(url, {"action": "unpublish", "version": record.lock_version}).status_code, 302
        )
        release.refresh_from_db()
        self.assertFalse(release.enabled)
        record.refresh_from_db()
        self.assertEqual(self.client.post(url, {"action": "archive", "version": record.lock_version}).status_code, 302)
        record.refresh_from_db()
        self.assertTrue(record.archived)
        self.assertContains(
            self.client.get(reverse("admin:catalog_relation_participant", args=[self.crop_entity.pk])), str(record.pk)
        )

    def test_editor_cannot_self_publish_and_current_material_is_checked_at_release(self):
        self.publication_fixture()
        record = self.create_draft()
        url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        response = self.client.post(url, {"action": "approve", "version": record.lock_version, "content_locale": "uk"})
        self.assertEqual(response.context["action"].errors.as_data()["action"][0].code, "invalid_choice")
        self.publication_rights(review=True, publish=True)
        for action in ("submit", "approve"):
            record.refresh_from_db()
            self.assertEqual(
                self.client.post(
                    url, {"action": action, "version": record.lock_version, "content_locale": "uk"}
                ).status_code,
                302,
            )
        record.refresh_from_db()
        type(self.post).objects.filter(pk=self.post.pk).update(text="Not reviewed")
        response = self.client.post(url, {"action": "publish", "version": record.lock_version, "content_locale": "uk"})
        self.assertContains(response, "An approved publication is unavailable")
        self.assertFalse(RelationRelease.objects.filter(record=record, enabled=True).exists())

    def test_reviewer_and_publisher_need_distinct_model_and_site_capabilities(self):
        self.publication_fixture()
        record = self.create_draft()
        url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        self.site_grant.can_review = True
        self.site_grant.can_publish = True
        self.site_grant.save()
        # Boolean grants alone do not add model permissions.
        page = self.client.get(url)
        self.assertNotIn("approve", [code for code, label in page.context["action"].fields["action"].choices])
        self.publication_rights(review=True)
        record.refresh_from_db()
        self.assertEqual(self.client.post(url, {"action": "submit", "version": record.lock_version}).status_code, 302)
        record.refresh_from_db()
        self.assertEqual(
            self.client.post(
                url, {"action": "approve", "version": record.lock_version, "content_locale": "uk"}
            ).status_code,
            302,
        )
        page = self.client.get(url)
        self.assertNotIn("publish", [code for code, label in page.context["action"].fields["action"].choices])
        self.assertFalse(RelationRelease.objects.exists())

    def test_review_capability_operates_without_draft_edit_permission(self):
        self.publication_fixture()
        self.assertEqual(
            self.client.post(
                self.add_url,
                self.draft_form(payload='{"evidence": "historical-payload"}'),
            ).status_code,
            302,
        )
        record = RelationRecord.objects.get()
        url = reverse("admin:catalog_relationrecord_change", args=[record.pk])
        self.assertEqual(
            self.client.post(
                url,
                self.draft_form(
                    version=record.lock_version,
                    payload='{"evidence": "submitted-payload"}',
                    source='{"evidence": "<script>source-marker</script>"}',
                    country="UA",
                    source_version_digest="a" * 64,
                ),
            ).status_code,
            302,
        )
        record.refresh_from_db()
        self.assertEqual(self.client.post(url, {"action": "submit", "version": record.lock_version}).status_code, 302)
        self.publication_rights(review=True)
        self.site_grant.can_edit = False
        self.site_grant.save(update_fields=["can_edit"])
        self.actor.user_permissions.remove(
            *Permission.objects.filter(
                content_type__app_label="catalog",
                codename__in=["add_relationrecord", "change_relationrecord"],
            )
        )
        record.refresh_from_db()
        page = self.client.get(url)
        self.assertIsNone(page.context["form"])
        for marker in ("historical-payload", "submitted-payload", "source-marker", "UA", "a" * 64):
            self.assertContains(page, marker)
        self.assertNotContains(page, "<script>source-marker</script>")
        response = self.client.post(url, {"action": "approve", "version": record.lock_version, "content_locale": "uk"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(record.revisions.order_by("-number").first().state, ReviewState.APPROVED)
        page = self.client.get(url)
        self.assertIsNone(page.context["form"])
        self.assertNotIn("publish", [code for code, label in page.context["action"].fields["action"].choices])
