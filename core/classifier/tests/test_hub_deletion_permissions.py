from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from core.classifier.admin import CategoryHubInline
from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class HubDeletionPermissionTests(TestCase):
    def setUp(self):
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root)
        self.owner = CategoryFactory(parent=self.crop)
        self.external = CategoryFactory(parent=self.root)
        self.target = CategoryFactory(parent=self.external)
        self.hub = CategoryHub.objects.create(category=self.owner)
        self.section = CategoryHubSection.objects.create(hub=self.hub, category=self.target, role="varieties")
        self.post = PostFactory(rubric=self.target)
        self.original_post = Post.objects.values().get(pk=self.post.pk)

    def login(self, *codenames):
        user = StaffUserFactory()
        user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
        self.client.force_login(user)
        return user

    def assert_preserved(self):
        self.assertTrue(CategoryHub.objects.filter(pk=self.hub.pk).exists())
        self.assertTrue(CategoryHubSection.objects.filter(pk=self.section.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def bulk(self, model, ids, confirmed=False):
        data = {"action": "delete_selected", "_selected_action": ids}
        if confirmed:
            data["post"] = "yes"
        return self.client.post(reverse(f"admin:classifier_{model}_changelist"), data)

    def test_single_and_bulk_hub_delete_require_child_permission(self):
        self.login("view_categoryhub", "delete_categoryhub")
        url = reverse("admin:classifier_categoryhub_delete", args=[self.hub.pk])
        for response in (
            self.client.get(url),
            self.client.post(url, {"post": "yes"}),
            self.bulk("categoryhub", [self.hub.pk]),
            self.bulk("categoryhub", [self.hub.pk], confirmed=True),
        ):
            self.assertEqual(response.status_code, 403)
            self.assert_preserved()

    def test_permitted_hub_delete_preserves_source_categories_and_posts(self):
        self.login("view_categoryhub", "delete_categoryhub", "delete_categoryhubsection")
        categories = list(Category.objects.values())
        url = reverse("admin:classifier_categoryhub_delete", args=[self.hub.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assertFalse(CategoryHub.objects.exists())
        self.assertFalse(CategoryHubSection.objects.exists())
        self.assertEqual(list(Category.objects.values()), categories)
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_mixed_bulk_hub_delete_is_all_or_nothing_and_allowed_with_child_permission(self):
        empty = CategoryHub.objects.create(category=self.crop)
        self.login("view_categoryhub", "delete_categoryhub")
        self.assertEqual(self.bulk("categoryhub", [empty.pk, self.hub.pk], confirmed=True).status_code, 403)
        self.assertTrue(CategoryHub.objects.filter(pk=empty.pk).exists())
        self.assert_preserved()
        self.login("view_categoryhub", "delete_categoryhub", "delete_categoryhubsection")
        self.assertEqual(self.bulk("categoryhub", [empty.pk, self.hub.pk], confirmed=True).status_code, 302)
        self.assertFalse(CategoryHub.objects.exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_empty_hub_can_be_deleted_without_child_permission(self):
        empty = CategoryHub.objects.create(category=self.crop)
        self.login("view_categoryhub", "delete_categoryhub")
        url = reverse("admin:classifier_categoryhub_delete", args=[empty.pk])
        self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 302)
        self.assert_preserved()

    def inline_data(self, response):
        self.owner.refresh_from_db()
        data = {
            "slug": self.owner.slug,
            "value": "Attempted category edit",
            "parent": self.owner.parent_id,
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
                "crop_hub-INITIAL_FORMS": 1,
                "crop_hub-0-id": self.hub.pk,
                "crop_hub-0-category": self.owner.pk,
                "crop_hub-0-description": "",
                "crop_hub-0-guide_category": "",
                "crop_hub-0-site": "",
                "crop_hub-0-locale": "",
                "crop_hub-0-DELETE": "on",
            }
        )
        return data

    def test_category_inline_hides_deletion_and_ignores_forged_delete_without_child_permission(self):
        self.login("change_category", "view_categoryhub", "change_categoryhub", "delete_categoryhub")
        url = reverse("admin:classifier_category_change", args=[self.owner.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'name="crop_hub-0-DELETE"')
        response = self.client.post(url, self.inline_data(response))
        self.assertEqual(response.status_code, 302)
        self.assert_preserved()

    def test_inline_server_guard_rolls_back_category_edit_if_delete_control_is_bypassed(self):
        self.login("change_category", "view_categoryhub", "change_categoryhub", "delete_categoryhub")
        url = reverse("admin:classifier_category_change", args=[self.owner.pk])
        # Simulate a stale/overridden UI permission decision: saving must still
        # recheck cascade permission inside the category form transaction.
        with patch.object(CategoryHubInline, "has_delete_permission", return_value=True):
            data = self.inline_data(self.client.get(url))
            self.assertEqual(self.client.post(url, data).status_code, 403)
        self.assertEqual(Category.objects.get(pk=self.owner.pk).value, self.owner.value)
        self.assert_preserved()

    def test_permitted_inline_delete_removes_configuration_only(self):
        self.login(
            "change_category",
            "view_categoryhub",
            "change_categoryhub",
            "delete_categoryhub",
            "delete_categoryhubsection",
        )
        url = reverse("admin:classifier_category_change", args=[self.owner.pk])
        response = self.client.get(url)
        self.assertContains(response, 'name="crop_hub-0-DELETE"')
        self.assertEqual(self.client.post(url, self.inline_data(response)).status_code, 302)
        self.assertFalse(CategoryHub.objects.exists())
        self.assertTrue(Category.objects.filter(pk=self.owner.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_owner_category_and_ancestor_single_and_confirmed_bulk_deletion_are_protected(self):
        self.login("view_category", "delete_category", "delete_categoryhub")
        unrelated = CategoryFactory(parent=self.root)
        for category in (self.owner, self.crop):
            url = reverse("admin:classifier_category_delete", args=[category.pk])
            for response in (
                self.client.get(url),
                self.client.post(url, {"post": "yes"}),
                self.bulk("category", [unrelated.pk, category.pk]),
                self.bulk("category", [unrelated.pk, category.pk], confirmed=True),
            ):
                self.assertEqual(response.status_code, 403)
                self.assertTrue(Category.objects.filter(pk=unrelated.pk).exists())
                self.assert_preserved()
        self.login("view_category", "delete_category", "delete_categoryhub", "delete_categoryhubsection")
        self.assertEqual(self.bulk("category", [self.crop.pk], confirmed=True).status_code, 302)
        self.assertFalse(Category.objects.filter(pk=self.owner.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.target.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_cross_branch_target_deletion_also_requires_reference_delete_permission(self):
        # Remove the target's article in setup: this test isolates deletion of a
        # category reference, rather than the independent article permissions.
        self.post.delete()
        self.login("view_category", "delete_category")
        for category in (self.target, self.external):
            url = reverse("admin:classifier_category_delete", args=[category.pk])
            self.assertEqual(self.client.post(url, {"post": "yes"}).status_code, 403)
            self.assertEqual(self.bulk("category", [category.pk], confirmed=True).status_code, 403)
            self.assertTrue(CategoryHubSection.objects.filter(pk=self.section.pk).exists())
        self.login("view_category", "delete_category", "delete_categoryhubsection")
        self.assertEqual(self.bulk("category", [self.external.pk], confirmed=True).status_code, 302)
        self.assertTrue(CategoryHub.objects.filter(pk=self.hub.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.owner.pk).exists())
        self.assertFalse(CategoryHubSection.objects.exists())

    def test_unrelated_category_deletion_does_not_require_hub_permissions(self):
        unrelated = CategoryFactory(parent=self.root)
        self.login("view_category", "delete_category")
        self.assertEqual(self.bulk("category", [unrelated.pk], confirmed=True).status_code, 302)
        self.assert_preserved()
