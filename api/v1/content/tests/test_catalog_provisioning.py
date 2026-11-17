from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.models import CatalogEntity
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class CatalogProvisioningTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="provisioning.example.test")
        self.enterContext(override_settings(SITE_ID=self.site.pk))
        self.operator = StaffUserFactory(is_superuser=True)
        self.editor = StaffUserFactory()
        self.editor.user_permissions.add(Permission.objects.get(codename="view_relationrecord"))
        self.site_grant = RelationSiteGrant.objects.create(actor=self.editor, site=self.site)
        self.crop = CategoryFactory()
        self.url = reverse("catalog-provision-entity")
        self.payload = {
            "site_grant_id": self.site_grant.pk,
            "anchor_type": "category",
            "anchor_id": self.crop.pk,
            "kind": "crop",
            "provenance": {"source": "test crop identity"},
        }
        self.client = self.token_client(self.operator)

    @staticmethod
    def token_client(actor):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=actor).key}")
        return client

    def provision(self, **overrides):
        return self.client.post(self.url, {**self.payload, **overrides}, format="json")

    def test_provisions_anchors_and_grants_readable_by_editor(self):
        crop = self.provision()
        self.assertEqual(crop.status_code, 201, crop.data)
        self.assertIn("no-store", crop["Cache-Control"])
        self.assertIn("noindex", crop["X-Robots-Tag"])
        self.crop.refresh_from_db()
        self.assertEqual(str(self.crop.entity_id), crop.data["entity_id"])
        self.assertEqual(self.crop.entity.created_by, self.operator)
        self.assertEqual(RelationEntityGrant.objects.get(pk=crop.data["entity_grant_id"]).category, self.crop)

        post = PostFactory(rubric=self.crop)
        prepared = self.provision(
            anchor_type="post",
            anchor_id=post.pk,
            kind="preparation",
            provenance={"formulation_identity": "fixture-123", "source": "test preparation identity"},
        )
        self.assertEqual(prepared.status_code, 201, prepared.data)
        self.assertEqual(RelationEntityGrant.objects.get(pk=prepared.data["entity_grant_id"]).post, post)
        listing = self.token_client(self.editor).get(reverse("catalog-entities"))
        self.assertEqual(listing.status_code, 200)
        self.assertSetEqual(
            {item["id"] for item in listing.data["results"]}, {crop.data["entity_id"], prepared.data["entity_id"]}
        )
        self.assertEqual(LogEntry.objects.filter(user=self.operator).count(), 6)

    def test_replay_preserves_identity_and_conflicts_roll_back(self):
        first = self.provision()
        retry = self.provision()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.data, first.data)
        other = CatalogEntity.objects.create(kind="crop", provenance={}, created_by=self.operator)
        explicit = {key: value for key, value in self.payload.items() if key != "provenance"}
        wrong = self.client.post(self.url, {**explicit, "entity_id": str(other.pk)}, format="json")
        self.assertEqual(wrong.status_code, 409)
        drift = self.provision(provenance={"source": "changed identity"})
        self.assertEqual(drift.status_code, 409)
        self.crop.refresh_from_db()
        self.assertEqual(str(self.crop.entity_id), first.data["entity_id"])
        self.assertEqual(RelationEntityGrant.objects.count(), 1)
        self.assertEqual(LogEntry.objects.filter(user=self.operator).count(), 3)

    def test_attaches_explicit_existing_identity_without_replacing_provenance(self):
        existing = CatalogEntity.objects.create(kind="crop", provenance={"source": "prior"}, created_by=self.operator)
        data = {key: value for key, value in self.payload.items() if key != "provenance"}
        result = self.client.post(self.url, {**data, "entity_id": str(existing.pk)}, format="json")
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.data["entity_id"], str(existing.pk))
        self.assertEqual(CatalogEntity.objects.count(), 1)

    def test_requires_superuser_and_a_site_grant_on_the_configured_site(self):
        self.editor.user_permissions.add(*Permission.objects.filter(content_type__model="relationentitygrant"))
        denied = self.token_client(self.editor).post(self.url, self.payload, format="json")
        self.assertEqual(denied.status_code, 403)
        foreign_site = Site.objects.create(domain="elsewhere.example.test")
        foreign = RelationSiteGrant.objects.create(actor=self.editor, site=foreign_site)
        self.assertEqual(self.provision(site_grant_id=foreign.pk).status_code, 404)
        self.assertEqual(self.provision(kind="preparation").status_code, 400)
        self.assertEqual(self.provision(site_id=foreign_site.pk).status_code, 400)
        self.assertFalse(CatalogEntity.objects.exists())
