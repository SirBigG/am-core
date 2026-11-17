from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.sites.models import Site
from django.test import TestCase, override_settings
from django.urls import reverse

from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.application_models import ApplicationReviewerGrant
from core.catalog.models import CatalogEntity
from core.catalog.relation_access import RelationAccess
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class CatalogGrantAdminTests(TestCase):
    def setUp(self):
        self.site = Site.objects.create(domain="grant-admin.example.test", name="Grant Admin")
        self.other_site = Site.objects.create(domain="other.example.test", name="Other")
        self.enterContext(override_settings(SITE_ID=self.site.pk))
        self.editor = StaffUserFactory()
        self.operator = StaffUserFactory(is_superuser=True)
        self.client.force_login(self.operator, backend="core.pro_auth.backends.AuthBackend")

    def add(self, model, **fields):
        return self.client.post(reverse(f"admin:catalog_{model}_add"), fields)

    def test_provisions_and_revokes_scoped_access(self):
        self.editor.user_permissions.add(Permission.objects.get(codename="view_relationrecord"))
        self.assertEqual(
            self.add(
                "relationsitegrant",
                actor=self.editor.pk,
                site=self.site.pk,
                can_edit=True,
                can_review=True,
                can_publish=True,
            ).status_code,
            302,
        )
        grant = RelationSiteGrant.objects.get(actor=self.editor, site=self.site)
        crop = CatalogEntity.objects.create(kind="crop", created_by=self.operator, provenance={})
        category = CategoryFactory(entity=crop)
        self.assertEqual(self.add("relationentitygrant", grant=grant.pk, category=category.pk).status_code, 302)
        preparation = CatalogEntity.objects.create(kind="preparation", created_by=self.operator, provenance={})
        post = PostFactory(entity=preparation, rubric=category)
        self.assertEqual(self.add("relationentitygrant", grant=grant.pk, post=post.pk).status_code, 302)
        self.assertEqual(
            self.add("applicationcountrypolicy", country="UA", timezone_name="Europe/Kyiv", active=True).status_code,
            302,
        )
        self.assertEqual(
            self.add("applicationreviewergrant", site_grant=grant.pk, country="UA", can_review=True).status_code,
            302,
        )

        access = RelationAccess(self.editor, self.site.pk)
        self.assertSetEqual(set(access.participants().values_list("entity_id", flat=True)), {crop.pk, preparation.pk})
        self.assertTrue(ApplicationReviewerGrant.objects.get(site_grant=grant, country_id="UA").can_review)
        self.assertTrue(LogEntry.objects.filter(user=self.operator, content_type__model="relationentitygrant").exists())

        url = reverse("admin:catalog_relationsitegrant_delete", args=[grant.pk])
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assertFalse(RelationEntityGrant.objects.filter(grant=grant).exists())
        self.assertFalse(ApplicationReviewerGrant.objects.filter(site_grant=grant).exists())

    def test_rejects_forged_site_and_mismatched_entity(self):
        response = self.add("relationsitegrant", actor=self.editor.pk, site=self.other_site.pk)
        self.assertIn("site", response.context["adminform"].form.errors)
        grant = RelationSiteGrant.objects.create(actor=self.editor, site=self.site)
        foreign_grant = RelationSiteGrant.objects.create(actor=self.editor, site=self.other_site)
        entity = CatalogEntity.objects.create(kind="crop", created_by=self.operator, provenance={})
        response = self.add("relationentitygrant", grant=foreign_grant.pk, entity=entity.pk)
        self.assertIn("grant", response.context["adminform"].form.errors)
        different_entity = CatalogEntity.objects.create(kind="crop", created_by=self.operator, provenance={})
        category = CategoryFactory(entity=different_entity)
        response = self.add("relationentitygrant", grant=grant.pk, entity=entity.pk, category=category.pk)
        self.assertIn("entity", response.context["adminform"].form.errors)
        self.assertFalse(RelationEntityGrant.objects.exists())

    def test_regular_staff_cannot_manage_grants_even_with_model_permissions(self):
        models = ("relationsitegrant", "relationentitygrant", "applicationreviewergrant", "applicationcountrypolicy")
        self.editor.user_permissions.add(
            *Permission.objects.filter(content_type__app_label="catalog", content_type__model__in=models)
        )
        self.client.force_login(self.editor, backend="core.pro_auth.backends.AuthBackend")
        for model in models:
            with self.subTest(model=model):
                self.assertEqual(self.client.get(reverse(f"admin:catalog_{model}_changelist")).status_code, 403)
                self.assertEqual(self.add(model).status_code, 403)
