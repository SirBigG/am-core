from unittest.mock import patch

from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from lxml import html

from core.classifier.models import Category, CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


@override_settings(HOST="https://agromega.in.ua")
class GuideHubPreviewTests(TestCase):
    permissions = (
        "classifier.view_category",
        "posts.view_guidesection",
        "posts.view_guidesectionarticle",
        "posts.view_post",
    )

    def setUp(self):
        cache.clear()
        self.crop = CategoryFactory(parent=CategoryFactory())
        self.hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.post = PostFactory(rubric=CategoryFactory(parent=self.crop), title="Existing public article")
        self.post_url = self.post.get_absolute_url()
        self.section = GuideSection.objects.create(category=self.hub, title="Planting", description="Saved description")
        self.placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.preview_url = reverse("admin:classifier_category_guide_preview", args=[self.hub.pk])
        self.public_url = reverse("posts-list-view", kwargs={"parent": self.crop.slug, "child": self.hub.slug})

    def staff(self, permissions=None, **kwargs):
        user = StaffUserFactory(**kwargs)
        for permission in self.permissions if permissions is None else permissions:
            app_label, codename = permission.split(".")
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return user

    def assert_private_headers(self, response):
        self.assertEqual(response.headers["X-Robots-Tag"], "noindex, nofollow")
        directives = {value.strip() for value in response.headers["Cache-Control"].split(",")}
        self.assertTrue({"no-store", "no-cache", "private", "max-age=0", "must-revalidate"}.issubset(directives))
        self.assertIn("Expires", response.headers)
        self.assertIn("Cookie", response.headers["Vary"])

    def test_authorized_view_only_editor_uses_same_renderer_and_public_content(self):
        self.client.force_login(self.staff())
        public = self.client.get(self.public_url)
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/guide_hub.html")
        self.assertContains(response, "Попередній перегляд збережених публічних матеріалів.")
        self.assertContains(response, self.post.title)
        self.assertContains(response, f'href="{self.post_url}"')
        self.assertEqual(response.context["guide_sections"], public.context["guide_sections"])
        self.assertEqual(response.context["object_list"], public.context["object_list"])
        self.assert_private_headers(response)

    def test_preview_has_noindex_meta_public_canonical_and_no_collection_sharing_metadata(self):
        self.client.force_login(self.staff())
        response = self.client.get(self.preview_url)
        document = html.fromstring(response.content)
        self.assertEqual(document.xpath('//meta[@name="robots"]/@content'), ["noindex,nofollow"])
        self.assertEqual(document.xpath('//link[@rel="canonical"]/@href'), ["https://agromega.in.ua" + self.public_url])
        self.assertFalse(document.xpath('//meta[@property="og:url"]'))
        self.assertNotContains(response, '"@type": "CollectionPage"')
        self.assertFalse(response.context["enable_analytics"])
        self.assertFalse(response.context["enable_adverts"])

    def test_anonymous_and_nonstaff_are_redirected_to_admin_login_with_private_headers(self):
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.headers["Location"])
        self.assert_private_headers(response)
        self.client.force_login(self.staff(is_staff=False))
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 302)
        self.assert_private_headers(response)

    def test_missing_each_required_model_permission_is_denied(self):
        for missing in self.permissions:
            with self.subTest(missing=missing):
                self.client.force_login(
                    self.staff([permission for permission in self.permissions if permission != missing])
                )
                response = self.client.get(self.preview_url)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, self.post.title, status_code=403)
                self.assert_private_headers(response)

    def test_change_permissions_also_allow_preview_without_separate_view_grants(self):
        self.client.force_login(
            self.staff(
                [
                    "classifier.change_category",
                    "posts.change_guidesection",
                    "posts.change_guidesectionarticle",
                    "posts.change_post",
                ]
            )
        )
        self.assertEqual(self.client.get(self.preview_url).status_code, 200)

    def test_category_object_permission_is_checked_after_model_permission(self):
        self.client.force_login(self.staff())
        with patch(
            "core.classifier.admin.CategoryAdmin.has_view_permission", side_effect=lambda request, obj=None: obj is None
        ):
            response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.post.title, status_code=403)
        self.assert_private_headers(response)

    def test_superuser_can_preview(self):
        self.client.force_login(self.staff([], is_superuser=True))
        self.assertEqual(self.client.get(self.preview_url).status_code, 200)

    def test_own_article_editor_can_preview_when_all_eligible_articles_are_owned(self):
        user = self.staff(
            [permission for permission in self.permissions if permission != "posts.view_post"]
            + ["posts.change_own_post"]
        )
        Post.objects.filter(pk=self.post.pk).update(publisher=user)
        self.client.force_login(user)
        response = self.client.get(self.preview_url)
        self.assertContains(response, self.post.title)
        self.assert_private_headers(response)

    def test_own_article_editor_cannot_preview_another_publishers_eligible_article(self):
        user = self.staff(
            [permission for permission in self.permissions if permission != "posts.view_post"]
            + ["posts.change_own_post"]
        )
        self.client.force_login(user)
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, self.post.title, status_code=403)
        self.assert_private_headers(response)

    def test_preview_link_is_on_saved_category_and_section_forms(self):
        self.client.force_login(self.staff())
        for url in (
            reverse("admin:classifier_category_change", args=[self.hub.pk]),
            reverse("admin:posts_guidesection_change", args=[self.section.pk]),
        ):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, f'href="{self.preview_url}"')

    def test_preview_link_is_hidden_without_placement_permissions_and_on_add_forms(self):
        self.client.force_login(self.staff(["classifier.change_category", "posts.change_guidesection"]))
        for url in (
            reverse("admin:classifier_category_change", args=[self.hub.pk]),
            reverse("admin:posts_guidesection_change", args=[self.section.pk]),
        ):
            response = self.client.get(url)
            self.assertNotContains(response, self.preview_url)
        self.client.force_login(self.staff([], is_superuser=True))
        response = self.client.get(reverse("admin:classifier_category_add"))
        self.assertNotContains(response, "Preview Guide Hub")

    def test_catalog_category_can_preview_saved_guide_without_switching_presentation(self):
        Category.objects.filter(pk=self.hub.pk).update(presentation_mode=CategoryPresentationMode.CATALOG)
        self.client.force_login(self.staff())
        response = self.client.get(self.preview_url)
        self.assertContains(response, self.post.title)
        self.assertTemplateUsed(response, "posts/guide_hub.html")
        public = self.client.get(self.public_url)
        self.assertTemplateUsed(public, "posts/list_order.html")
        self.assertNotContains(public, "Попередній перегляд збережених публічних матеріалів.")

    def test_preview_obeys_public_eligibility_and_does_not_bypass_inactive_categories(self):
        hidden = GuideSection.objects.create(category=self.hub, title="Hidden section", is_active=False)
        GuideSectionArticle.objects.create(section=hidden, post=self.post)
        hidden_post = PostFactory(rubric=self.post.rubric, title="Unpublished article", status=False)
        GuideSectionArticle.objects.create(section=self.section, post=hidden_post)
        self.client.force_login(self.staff())
        response = self.client.get(self.preview_url)
        self.assertContains(response, self.post.title)
        self.assertNotContains(response, hidden.title)
        self.assertNotContains(response, hidden_post.title)
        Category.objects.filter(pk=self.crop.pk).update(is_active=False)
        response = self.client.get(self.preview_url)
        self.assertContains(response, "Матеріали посібника готуються до публікації.")
        self.assertNotContains(response, self.post.title)
        self.assertEqual(self.client.get(self.public_url).status_code, 404)

    def test_preview_does_not_persist_submitted_changes_or_generate_article_urls(self):
        Post.objects.filter(pk=self.post.pk).update(absolute_url="")
        snapshots = {
            model: list(model.objects.values()) for model in (Category, GuideSection, GuideSectionArticle, Post)
        }
        self.client.force_login(self.staff())
        response = self.client.get(self.preview_url, {"title": "Unsaved title", "is_active": "0"})
        self.assertContains(response, self.section.title)
        self.assertNotContains(response, "Unsaved title")
        for model, rows in snapshots.items():
            self.assertEqual(list(model.objects.values()), rows)

    def test_preview_reads_fresh_data_and_does_not_reuse_another_users_response(self):
        self.client.force_login(self.staff())
        self.assertContains(self.client.get(self.preview_url), "Saved description")
        GuideSection.objects.filter(pk=self.section.pk).update(description="New saved description")
        response = self.client.get(self.preview_url, headers={"if-none-match": '"old-preview"'})
        self.assertContains(response, "New saved description")
        self.assert_private_headers(response)
        self.client.force_login(self.staff([]))
        response = self.client.get(self.preview_url)
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "New saved description", status_code=403)
        self.assert_private_headers(response)

    def test_head_is_allowed_post_is_rejected_and_error_responses_are_private(self):
        self.client.force_login(self.staff())
        response = self.client.head(self.preview_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")
        self.assert_private_headers(response)
        response = self.client.post(self.preview_url, {"title": "Must not save"})
        self.assertEqual(response.status_code, 405)
        self.assert_private_headers(response)
        for category_id in (999999999, "invalid-id", self.crop.parent_id):
            response = self.client.get(reverse("admin:classifier_category_guide_preview", args=[category_id]))
            self.assertEqual(response.status_code, 404)
            self.assert_private_headers(response)

    def test_public_route_cannot_enable_admin_preview_with_query_parameters(self):
        hidden = GuideSection.objects.create(category=self.hub, title="Private section", is_active=False)
        GuideSectionArticle.objects.create(section=hidden, post=self.post)
        response = self.client.get(self.public_url, {"preview": "1", "is_guide_preview": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, hidden.title)
        self.assertNotContains(response, "Попередній перегляд збережених публічних матеріалів.")
        self.assertNotIn("X-Robots-Tag", response.headers)
