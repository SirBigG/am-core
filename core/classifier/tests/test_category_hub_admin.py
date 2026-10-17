from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.utils.tests.factories import CategoryFactory, StaffUserFactory


class CategoryHubConfigurationTests(TestCase):
    def setUp(self):
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root)
        self.catalog = CategoryFactory(parent=self.crop)
        self.other = CategoryFactory(parent=self.root)
        self.hub = CategoryHub.objects.create(category=self.crop)

    def test_inactive_by_default_and_references_existing_categories(self):
        self.assertFalse(self.hub.is_active)
        self.assertEqual(self.hub.category_id, self.crop.pk)
        with self.assertRaises(ValidationError):
            CategoryHub(category=self.crop).full_clean()

    def test_section_rejects_recursive_targets_including_on_unsaved_hub(self):
        for target in (self.crop, self.root):
            with self.subTest(target=target.pk):
                with self.assertRaises(ValidationError):
                    CategoryHubSection(hub=self.hub, category=target).full_clean()
        unsaved = CategoryHub(category=self.crop)
        with self.assertRaises(ValidationError):
            CategoryHubSection(hub=unsaved, category=self.root).clean()
        CategoryHubSection(hub=self.hub, category=self.catalog).full_clean()

    def test_explicit_guide_source_can_cross_categories(self):
        self.hub.guide_category = self.other
        self.hub.full_clean()
        self.hub.guide_category = self.crop
        self.hub.full_clean()
        self.hub.guide_category = self.catalog
        self.hub.full_clean()

    def test_primary_role_and_target_unique_with_multiple_extra_sections_allowed(self):
        CategoryHubSection.objects.create(hub=self.hub, category=self.catalog, role="varieties")
        another = CategoryFactory(parent=self.crop)
        for values in ({"category": another, "role": "varieties"}, {"category": self.catalog, "role": "pests"}):
            with self.subTest(values=values):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    CategoryHubSection.objects.create(hub=self.hub, **values)
        CategoryHubSection.objects.create(hub=self.hub, category=another)
        CategoryHubSection.objects.create(hub=self.hub, category=CategoryFactory(parent=self.crop))
        self.assertEqual(self.hub.sections.count(), 3)

    def test_config_removal_preserves_taxonomy(self):
        original = list(Category.objects.values())
        CategoryHubSection.objects.create(hub=self.hub, category=self.catalog)
        self.hub.delete()
        self.assertEqual(list(Category.objects.values()), original)


class CategoryHubAdminTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = StaffUserFactory(is_superuser=True)
        self.client.force_login(self.user)
        self.crop = CategoryFactory(parent=CategoryFactory())
        self.catalog = CategoryFactory(parent=self.crop)
        self.other = CategoryFactory()
        # Inserting another root can renumber this tree; URL ancestry must use
        # the current MPTT coordinates rather than the factory's stale instance.
        self.crop.refresh_from_db()
        self.add_url = reverse("admin:classifier_categoryhub_add")

    def data(self, category=None):
        return {
            "category": self.crop.pk,
            "is_active": "on",
            "description": "Admin introduction",
            "guide_category": "",
            "site": "",
            "locale": "",
            "sections-TOTAL_FORMS": 1,
            "sections-INITIAL_FORMS": 0,
            "sections-MIN_NUM_FORMS": 0,
            "sections-MAX_NUM_FORMS": 1000,
            "sections-0-category": (category or self.catalog).pk,
            "sections-0-role": "varieties",
            "sections-0-title": "Catalog from admin",
            "sections-0-description": "Purpose",
            "sections-0-sort_order": 1,
            "sections-0-is_active": "on",
            "_save": "Save",
        }

    def test_admin_can_select_market_widget_category(self):
        data = self.data()
        data["market_category"] = self.other.pk
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 302)
        hub = CategoryHub.objects.get(category=self.crop)
        self.assertEqual(hub.market_category_id, self.other.pk)
        response = self.client.get(reverse("admin:classifier_categoryhub_change", args=[hub.pk]))
        self.assertContains(response, 'name="market_category"')

    def test_create_hub_and_inline_then_edit_public_configuration(self):
        original = list(Category.objects.values())
        response = self.client.post(self.add_url, self.data())
        self.assertEqual(response.status_code, 302)
        hub = CategoryHub.objects.get(category=self.crop)
        self.assertEqual(hub.sections.get().category_id, self.catalog.pk)
        self.assertEqual(list(Category.objects.values()), original)
        response = self.client.get(self.crop.get_absolute_url())
        self.assertContains(response, "Admin introduction")
        self.assertContains(response, "Catalog from admin")
        url = reverse("admin:classifier_categoryhub_change", args=[hub.pk])
        data = self.data()
        data.update(
            {
                "description": "Changed without restart",
                "sections-INITIAL_FORMS": 1,
                "sections-0-id": hub.sections.get().pk,
            }
        )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        self.assertContains(self.client.get(self.crop.get_absolute_url()), "Changed without restart")

    def test_recursive_target_cannot_be_saved_through_admin(self):
        response = self.client.post(self.add_url, self.data(self.crop))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CategoryHub.objects.exists())
        self.assertContains(response, "Choose a section category other than this hub")

    def test_section_formset_rejects_duplicate_roles(self):
        data = self.data()
        second = CategoryFactory(parent=self.crop)
        data["sections-TOTAL_FORMS"] = 2
        for field in ("role", "title", "description", "sort_order", "is_active"):
            data[f"sections-1-{field}"] = data[f"sections-0-{field}"]
        data["sections-1-category"] = second.pk
        response = self.client.post(self.add_url, data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CategoryHub.objects.exists())

    def test_category_change_has_hub_inline_and_link_to_section_editor(self):
        hub = CategoryHub.objects.create(category=self.crop)
        response = self.client.get(reverse("admin:classifier_category_change", args=[self.crop.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="crop_hub-0-is_active"')
        self.assertContains(response, reverse("admin:classifier_categoryhub_change", args=[hub.pk]))

    def test_staff_without_hub_permissions_cannot_configure_it(self):
        user = StaffUserFactory()
        user.user_permissions.add(Permission.objects.get(codename="change_category"))
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.add_url).status_code, 403)
        self.assertEqual(self.client.post(self.add_url, self.data()).status_code, 403)
        response = self.client.get(reverse("admin:classifier_category_change", args=[self.crop.pk]))
        self.assertNotContains(response, 'name="crop_hub-0-is_active"')
        self.assertFalse(CategoryHub.objects.exists())

    def test_category_inline_can_create_disabled_configuration(self):
        url = reverse("admin:classifier_category_change", args=[self.crop.pk])
        response = self.client.get(url)
        data = {
            "value": self.crop.value,
            "slug": self.crop.slug,
            "parent": self.crop.parent_id,
            "presentation_mode": "catalog",
            "is_active": "on",
            "_save": "Save",
        }
        for inline in response.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            data.update({f"{prefix}-TOTAL_FORMS": 0, f"{prefix}-INITIAL_FORMS": 0})
        data.update(
            {
                "crop_hub-TOTAL_FORMS": 1,
                "crop_hub-0-description": "Prepared in category admin",
                "crop_hub-0-category": self.crop.pk,
                "crop_hub-0-guide_category": "",
                "crop_hub-0-site": "",
                "crop_hub-0-locale": "",
            }
        )
        self.assertEqual(self.client.post(url, data).status_code, 302)
        hub = CategoryHub.objects.get(category=self.crop)
        self.assertFalse(hub.is_active)
        self.assertEqual(hub.description, "Prepared in category admin")
