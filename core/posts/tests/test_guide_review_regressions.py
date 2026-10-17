from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.test import TestCase, override_settings
from django.urls import reverse

from core.classifier.models import Category, CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class GuideAdminReviewRegressionTests(TestCase):
    def setUp(self):
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root)
        self.hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.owner = CategoryFactory(parent=CategoryFactory())
        self.post = PostFactory(rubric=self.owner, status=False, title="UNPUBLISHED_OTHER_AUTHOR_TITLE")
        self.post.get_absolute_url()
        self.original_post = Post.objects.values().get(pk=self.post.pk)
        self.section = GuideSection.objects.create(category=self.hub, title="Planting")
        self.placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.category_url = reverse("admin:classifier_category_change", args=[self.hub.pk])
        self.section_url = reverse("admin:posts_guidesection_change", args=[self.section.pk])

    def staff(self, *permissions):
        user = StaffUserFactory()
        for name in permissions:
            app, codename = name.split(".")
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
        return user

    def assert_article_and_placement_unchanged(self):
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)
        self.assertTrue(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assertTrue(GuideSectionArticle.objects.filter(pk=self.placement.pk).exists())

    def inline_delete_data(self):
        return {
            "value": self.hub.value,
            "slug": self.hub.slug,
            "parent": self.crop.pk,
            "is_active": "on",
            "presentation_mode": self.hub.presentation_mode,
            "_save": "Save",
            "guide_sections-TOTAL_FORMS": 1,
            "guide_sections-INITIAL_FORMS": 1,
            "guide_sections-0-id": self.section.pk,
            "guide_sections-0-DELETE": "on",
        }

    def test_category_inline_cannot_delete_placements_without_child_delete_permission(self):
        self.client.force_login(
            self.staff("classifier.change_category", "posts.view_guidesection", "posts.delete_guidesection")
        )
        response = self.client.get(self.category_url)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="guide_sections-0-DELETE"')
        response = self.client.post(self.category_url, self.inline_delete_data())
        self.assertEqual(response.status_code, 302)
        self.assert_article_and_placement_unchanged()

    def test_category_inline_rechecks_article_scope_and_rolls_back_category_changes(self):
        self.client.force_login(
            self.staff(
                "classifier.change_category",
                "posts.view_guidesection",
                "posts.delete_guidesection",
                "posts.delete_guidesectionarticle",
                "posts.change_own_post",
            )
        )
        data = self.inline_delete_data()
        data["value"] = "Must roll back"
        response = self.client.post(self.category_url, data)
        self.assertEqual(response.status_code, 403)
        self.hub.refresh_from_db()
        self.assertNotEqual(self.hub.value, "Must roll back")
        self.assert_article_and_placement_unchanged()

    def test_authorized_inline_deletion_preserves_external_article_and_url(self):
        self.client.force_login(
            self.staff(
                "classifier.change_category",
                "posts.view_guidesection",
                "posts.delete_guidesection",
                "posts.delete_guidesectionarticle",
                "posts.view_post",
            )
        )
        response = self.client.post(self.category_url, self.inline_delete_data())
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(self.post.guide_placements.exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_section_single_and_bulk_delete_require_placement_delete_permission(self):
        self.client.force_login(self.staff("posts.view_guidesection", "posts.delete_guidesection", "posts.view_post"))
        url = reverse("admin:posts_guidesection_delete", args=[self.section.pk])
        for method, data in ((self.client.get, {}), (self.client.post, {"post": "yes"})):
            self.assertEqual(method(url, data).status_code, 403)
        for confirmation in ({}, {"post": "yes"}):
            response = self.client.post(
                reverse("admin:posts_guidesection_changelist"),
                {
                    "action": "delete_selected",
                    "_selected_action": [self.section.pk],
                    **confirmation,
                },
            )
            self.assertEqual(response.status_code, 403)
        self.assert_article_and_placement_unchanged()

    def test_category_and_ancestor_deletion_trees_cannot_disclose_hidden_article_titles(self):
        self.client.force_login(
            self.staff(
                "classifier.view_category",
                "classifier.delete_category",
                "posts.delete_guidesection",
                "posts.delete_guidesectionarticle",
                "posts.change_own_post",
            )
        )
        for category in (self.hub, self.crop, self.root):
            with self.subTest(category=category.pk):
                url = reverse("admin:classifier_category_delete", args=[category.pk])
                for method, data in ((self.client.get, {}), (self.client.post, {"post": "yes"})):
                    response = method(url, data)
                    self.assertEqual(response.status_code, 403)
                    self.assertNotContains(response, self.post.title, status_code=403)
                for confirmation in ({}, {"post": "yes"}):
                    response = self.client.post(
                        reverse("admin:classifier_category_changelist"),
                        {
                            "action": "delete_selected",
                            "_selected_action": [category.pk],
                            **confirmation,
                        },
                    )
                    self.assertEqual(response.status_code, 403)
                    self.assertNotContains(response, self.post.title, status_code=403)
        self.assert_article_and_placement_unchanged()

    def test_category_confirmed_bulk_delete_cannot_bypass_child_permissions(self):
        self.client.force_login(
            self.staff(
                "classifier.view_category",
                "classifier.delete_category",
                "posts.delete_guidesection",
                "posts.view_post",
            )
        )
        for category in (self.hub, self.crop):
            for confirmation in ({}, {"post": "yes"}):
                response = self.client.post(
                    reverse("admin:classifier_category_changelist"),
                    {
                        "action": "delete_selected",
                        "_selected_action": [category.pk],
                        **confirmation,
                    },
                )
                self.assertEqual(response.status_code, 403)
        self.assert_article_and_placement_unchanged()

    def test_mixed_bulk_selection_is_validated_before_any_category_is_deleted(self):
        user = self.staff(
            "classifier.view_category",
            "classifier.delete_category",
            "posts.delete_guidesection",
            "posts.delete_guidesectionarticle",
            "posts.change_own_post",
        )
        own_hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        own_section = GuideSection.objects.create(category=own_hub, title="Visible guide")
        own_post = PostFactory(publisher=user, rubric=self.owner)
        own_original = Post.objects.values().get(pk=own_post.pk)
        GuideSectionArticle.objects.create(section=own_section, post=own_post)
        self.client.force_login(user)
        response = self.client.post(
            reverse("admin:classifier_category_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [own_hub.pk, self.hub.pk],
                "post": "yes",
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Category.objects.filter(pk=own_hub.pk).exists())
        self.assertTrue(GuideSection.objects.filter(pk=own_section.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=own_post.pk), own_original)
        self.assert_article_and_placement_unchanged()

    def test_authorized_category_deletion_preserves_external_article(self):
        self.client.force_login(
            self.staff(
                "classifier.view_category",
                "classifier.delete_category",
                "posts.delete_guidesection",
                "posts.delete_guidesectionarticle",
                "posts.view_post",
            )
        )
        response = self.client.post(reverse("admin:classifier_category_delete", args=[self.hub.pk]), {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=self.hub.pk).exists())
        self.assertFalse(self.post.guide_placements.exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_authorized_bulk_category_deletion_keeps_external_article_and_other_trees(self):
        self.client.force_login(
            self.staff(
                "classifier.view_category",
                "classifier.delete_category",
                "posts.delete_guidesection",
                "posts.delete_guidesectionarticle",
                "posts.view_post",
            )
        )
        response = self.client.post(
            reverse("admin:classifier_category_changelist"),
            {
                "action": "delete_selected",
                "_selected_action": [self.crop.pk],
                "post": "yes",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Category.objects.filter(pk=self.hub.pk).exists())
        self.assertTrue(Category.objects.filter(pk=self.owner.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_history_scope_includes_titles_from_removed_placements_without_erasing_logs(self):
        self.client.force_login(StaffUserFactory(is_superuser=True))
        data = {
            "category": self.hub.pk,
            "title": self.section.title,
            "description": "",
            "sort_order": 10,
            "is_active": "on",
            "articles-TOTAL_FORMS": 1,
            "articles-INITIAL_FORMS": 1,
            "articles-0-id": self.placement.pk,
            "articles-0-post": self.post.pk,
            "articles-0-sort_order": 10,
            "_save": "Save",
        }
        self.assertEqual(self.client.post(self.section_url, data).status_code, 302)
        history_url = reverse("admin:posts_guidesection_history", args=[self.section.pk])
        original_logs = list(LogEntry.objects.values())
        self.assertTrue(any(self.post.title in entry["change_message"] for entry in original_logs))
        scoped_user = self.staff("posts.view_guidesection", "posts.view_guidesectionarticle", "posts.change_own_post")
        self.client.force_login(scoped_user)
        self.assertNotContains(self.client.get(self.section_url), self.post.title)
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.post.title, status_code=403)
        self.placement.delete()
        response = self.client.get(history_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.post.title, status_code=403)
        self.assertEqual(list(LogEntry.objects.values()), original_logs)
        self.client.force_login(self.staff("posts.view_guidesection", "posts.view_post"))
        self.assertContains(self.client.get(history_url), self.post.title)
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)


@override_settings(HOST="https://agromega.in.ua")
class GuideSEOReviewRegressionTests(TestCase):
    def setUp(self):
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root)
        self.hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.hub.refresh_from_db()
        self.url = reverse("posts-list-view", kwargs={"parent": self.crop.slug, "child": self.hub.slug})
        self.list_url = reverse("posts-list-child", kwargs={"parent": self.crop.slug, "child": self.hub.slug})

    def test_sitemap_guide_visibility_matches_own_and_ancestor_activity(self):
        self.assertContains(self.client.get("/sitemap-main.xml"), "https://agromega.in.ua" + self.url)
        for category in (self.hub, self.crop, self.root):
            with self.subTest(category=category.pk):
                Category.objects.filter(pk=category.pk).update(is_active=False)
                self.assertEqual(self.client.get(self.url).status_code, 404)
                self.assertNotContains(self.client.get("/sitemap-main.xml"), "https://agromega.in.ua" + self.url)
                Category.objects.filter(pk=category.pk).update(is_active=True)
                self.assertEqual(self.client.get(self.url).status_code, 200)
                self.assertContains(self.client.get("/sitemap-main.xml"), "https://agromega.in.ua" + self.url)

    def test_sitemap_catalog_behavior_and_unrelated_inactive_trees_are_unchanged(self):
        catalog = CategoryFactory(parent=self.crop)
        catalog.refresh_from_db()
        CategoryFactory(is_active=False)
        sitemap = self.client.get("/sitemap-main.xml")
        self.assertContains(sitemap, "https://agromega.in.ua" + self.url)
        Category.objects.filter(pk=self.crop.pk).update(is_active=False)
        sitemap = self.client.get("/sitemap-main.xml")
        self.assertNotContains(sitemap, "https://agromega.in.ua" + self.url)
        self.assertContains(sitemap, "https://agromega.in.ua" + catalog.absolute_url)

    def test_catalog_guide_catalog_cycle_restores_list_without_permanent_redirect(self):
        post = PostFactory(rubric=self.hub)
        post.get_absolute_url()
        original = Post.objects.values().get(pk=post.pk)
        for mode in (
            CategoryPresentationMode.CATALOG,
            CategoryPresentationMode.GUIDE_HUB,
            CategoryPresentationMode.CATALOG,
        ):
            Category.objects.filter(pk=self.hub.pk).update(presentation_mode=mode)
            for method in (self.client.get, self.client.head):
                response = method(self.list_url + "?page=1&order=title")
                if mode == CategoryPresentationMode.GUIDE_HUB:
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.headers["Location"], self.url)
                    self.assertIn("no-store", response.headers["Cache-Control"])
                    self.assertIn("no-cache", response.headers["Cache-Control"])
                    self.assertIn("Expires", response.headers)
                else:
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, "posts/list.html")
                    self.assertEqual(response.context["paginator"].per_page, 50)
        self.assertEqual(Post.objects.values().get(pk=post.pk), original)
