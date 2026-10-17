from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from core.classifier.models import CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


class GuideAdminTests(TestCase):
    def setUp(self):
        self.superuser = StaffUserFactory(is_superuser=True)
        self.client.force_login(self.superuser)
        self.crop = CategoryFactory(parent=CategoryFactory())
        self.hub = CategoryFactory(parent=self.crop, presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        self.owner = CategoryFactory(parent=self.crop)
        self.post = PostFactory(rubric=self.owner, title="Existing article", status=False)
        self.post.get_absolute_url()
        self.original_post = Post.objects.values().get(pk=self.post.pk)
        self.section = GuideSection.objects.create(category=self.hub, title="Planting")
        self.change_url = reverse("admin:posts_guidesection_change", args=[self.section.pk])

    def staff(self, *permissions):
        user = StaffUserFactory()
        for permission in permissions:
            app_label, codename = permission.split(".")
            user.user_permissions.add(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        return user

    def section_data(self, rows=(), initial=0):
        data = {
            "category": self.hub.pk,
            "title": self.section.title,
            "description": "Section description",
            "sort_order": 10,
            "is_active": "on",
            "articles-TOTAL_FORMS": len(rows),
            "articles-INITIAL_FORMS": initial,
            "articles-MIN_NUM_FORMS": 0,
            "articles-MAX_NUM_FORMS": 1000,
            "_save": "Save",
        }
        for index, row in enumerate(rows):
            for key, value in row.items():
                data[f"articles-{index}-{key}"] = value
        return data

    def assert_post_unchanged(self):
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_category_inline_creates_orders_edits_and_deletes_sections(self):
        url = reverse("admin:classifier_category_change", args=[self.hub.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "presentation_mode")
        self.assertContains(response, self.change_url)
        data = {
            "value": self.hub.value,
            "slug": self.hub.slug,
            "parent": self.crop.pk,
            "presentation_mode": CategoryPresentationMode.GUIDE_HUB,
            "is_active": "on",
            "_save": "Save",
        }
        for inline in response.context["inline_admin_formsets"]:
            prefix = inline.formset.prefix
            data.update({f"{prefix}-TOTAL_FORMS": 0, f"{prefix}-INITIAL_FORMS": 0})
        data.update(
            {
                "guide_sections-TOTAL_FORMS": 2,
                "guide_sections-INITIAL_FORMS": 1,
                "guide_sections-0-id": self.section.pk,
                "guide_sections-0-title": "Seed preparation",
                "guide_sections-0-description": "Updated description",
                "guide_sections-0-sort_order": 20,
                "guide_sections-0-is_active": "on",
                "guide_sections-1-title": "Planning",
                "guide_sections-1-description": "",
                "guide_sections-1-sort_order": 10,
                "guide_sections-1-is_active": "on",
            }
        )
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(self.hub.guide_sections.values_list("title", flat=True)), ["Planning", "Seed preparation"]
        )
        self.assert_post_unchanged()
        self.section.refresh_from_db()
        self.assertEqual(self.section.description, "Updated description")
        planning = self.hub.guide_sections.get(title="Planning")
        data.update(
            {"guide_sections-INITIAL_FORMS": 2, "guide_sections-1-id": planning.pk, "guide_sections-0-DELETE": "on"}
        )
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assertFalse(self.post.guide_placements.exists())
        self.assert_post_unchanged()

    def test_section_admin_creates_empty_section_with_category_autocomplete(self):
        url = reverse("admin:posts_guidesection_add")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-field-name="category"')
        self.assertContains(response, 'data-field-name="post"')
        response = self.client.post(url, self.section_data())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.hub.guide_sections.count(), 2)

    def test_placements_add_reorder_and_delete_without_changing_article(self):
        second_post = PostFactory(rubric=self.owner)
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"post": self.post.pk, "sort_order": 20},
                    {"post": second_post.pk, "sort_order": 10},
                ]
            ),
        )
        self.assertEqual(response.status_code, 302)
        placements = list(self.section.articles.all())
        self.assertEqual([item.post_id for item in placements], [second_post.pk, self.post.pk])
        self.assert_post_unchanged()
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"id": placements[0].pk, "post": second_post.pk, "sort_order": 30},
                    {"id": placements[1].pk, "post": self.post.pk, "sort_order": 0},
                ],
                initial=2,
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(self.section.articles.values_list("post_id", flat=True)), [self.post.pk, second_post.pk])
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"id": placements[1].pk, "post": self.post.pk, "sort_order": 0, "DELETE": "on"},
                    {"id": placements[0].pk, "post": second_post.pk, "sort_order": 30},
                ],
                initial=2,
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(self.section.articles.values_list("post_id", flat=True)), [second_post.pk])
        self.assert_post_unchanged()

    def test_duplicate_placements_are_form_errors_and_save_nothing(self):
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"post": self.post.pk, "sort_order": 0},
                    {"post": self.post.pk, "sort_order": 10},
                ]
            ),
        )
        self.assertEqual(response.status_code, 200)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertTrue(formset.non_form_errors())
        self.assertFalse(self.section.articles.exists())
        self.assert_post_unchanged()

    def test_article_can_be_assigned_to_sections_in_other_categories(self):
        other_hub = CategoryFactory(presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        other_section = GuideSection.objects.create(category=other_hub, title="Another guide")
        for section in (self.section, other_section):
            data = self.section_data([{"post": self.post.pk, "sort_order": 0}])
            data["category"] = section.category_id
            response = self.client.post(reverse("admin:posts_guidesection_change", args=[section.pk]), data)
            self.assertEqual(response.status_code, 302)
        self.assertEqual(self.post.guide_placements.count(), 2)
        self.assert_post_unchanged()

    def test_section_delete_confirmation_removes_only_collection_rows(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        url = reverse("admin:posts_guidesection_delete", args=[self.section.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assert_post_unchanged()
        response = self.client.post(url, {"post": "yes"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.post.guide_placements.exists())
        self.assert_post_unchanged()

    def test_staff_without_guide_permissions_cannot_manage_sections(self):
        user = self.staff("posts.change_own_post")
        self.client.force_login(user)
        for url in (
            self.change_url,
            reverse("admin:posts_guidesection_add"),
            reverse("admin:posts_guidesection_changelist"),
        ):
            self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(self.change_url, self.section_data()).status_code, 403)

    def test_category_permission_does_not_grant_section_inline_editing(self):
        self.client.force_login(self.staff("classifier.change_category"))
        url = reverse("admin:classifier_category_change", args=[self.hub.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(
            "guide_sections", [inline.formset.prefix for inline in response.context["inline_admin_formsets"]]
        )
        response = self.client.post(
            url,
            {
                "value": self.hub.value,
                "slug": self.hub.slug,
                "parent": self.crop.pk,
                "is_active": "on",
                "presentation_mode": self.hub.presentation_mode,
                "_save": "Save",
                "guide_sections-TOTAL_FORMS": 1,
                "guide_sections-INITIAL_FORMS": 1,
                "guide_sections-0-id": self.section.pk,
                "guide_sections-0-title": "Unauthorized change",
                "guide_sections-0-sort_order": 0,
                "guide_sections-0-is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.section.refresh_from_db()
        self.assertEqual(self.section.title, "Planting")

    def test_view_only_permissions_do_not_allow_section_writes(self):
        self.client.force_login(
            self.staff("posts.view_guidesection", "posts.view_guidesectionarticle", "posts.view_post")
        )
        self.assertEqual(self.client.get(self.change_url).status_code, 200)
        self.assertEqual(self.client.post(self.change_url, self.section_data()).status_code, 403)

    def test_section_change_permission_does_not_grant_placement_permissions(self):
        self.client.force_login(self.staff("posts.change_guidesection", "posts.view_post"))
        response = self.client.get(self.change_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["inline_admin_formsets"])
        response = self.client.post(self.change_url, self.section_data([{"post": self.post.pk, "sort_order": 0}]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.section.articles.exists())

    def autocomplete(self, term=""):
        return self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "posts",
                "model_name": "guidesectionarticle",
                "field_name": "post",
                "term": term,
            },
        )

    def own_editor(self):
        return self.staff(
            "posts.change_own_post",
            "posts.change_guidesection",
            "posts.view_guidesectionarticle",
            "posts.add_guidesectionarticle",
            "posts.change_guidesectionarticle",
            "posts.delete_guidesectionarticle",
        )

    def test_autocomplete_and_inline_rows_follow_existing_own_post_scope(self):
        user = self.own_editor()
        own_post = PostFactory(publisher=user, rubric=self.owner, title="Own selectable article")
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        own_placement = GuideSectionArticle.objects.create(section=self.section, post=own_post)
        self.client.force_login(user)
        response = self.autocomplete()
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["results"]], [str(own_post.pk)])
        response = self.client.get(self.change_url)
        self.assertNotContains(response, self.post.title)
        formset = response.context["inline_admin_formsets"][0].formset
        self.assertEqual(list(formset.queryset), [own_placement])
        self.assertEqual(list(formset.forms[0].fields["post"].queryset), [own_post])

    def test_autocomplete_reuses_post_search_and_global_view_permission(self):
        self.client.force_login(self.staff("posts.view_post", "posts.view_guidesection"))
        response = self.autocomplete("Existing")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.json()["results"]], [str(self.post.pk)])

    def test_no_article_view_permission_denies_autocomplete_and_forged_assignment(self):
        user = self.staff("posts.change_guidesection", "posts.add_guidesectionarticle")
        self.client.force_login(user)
        self.assertEqual(self.autocomplete().status_code, 403)
        response = self.client.post(self.change_url, self.section_data([{"post": self.post.pk, "sort_order": 0}]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["inline_admin_formsets"][0].formset.errors[0]["post"])
        self.assertFalse(self.section.articles.exists())
        self.assert_post_unchanged()

    def test_own_editor_cannot_forge_another_publishers_post_id(self):
        self.client.force_login(self.own_editor())
        response = self.client.post(self.change_url, self.section_data([{"post": self.post.pk, "sort_order": 0}]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["inline_admin_formsets"][0].formset.errors[0]["post"])
        self.assertFalse(self.section.articles.exists())
        self.assert_post_unchanged()

    def test_own_editor_can_assign_owned_post_without_changing_either_article(self):
        user = self.own_editor()
        own_post = PostFactory(publisher=user, rubric=self.owner)
        original = Post.objects.values().get(pk=own_post.pk)
        self.client.force_login(user)
        response = self.client.post(self.change_url, self.section_data([{"post": own_post.pk, "sort_order": 0}]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.section.articles.get().post_id, own_post.pk)
        self.assertEqual(Post.objects.values().get(pk=own_post.pk), original)
        self.assert_post_unchanged()

    def test_own_editor_cannot_delete_hidden_placement_with_forged_inline_id(self):
        hidden = GuideSectionArticle.objects.create(section=self.section, post=self.post, sort_order=20)
        user = self.own_editor()
        own_post = PostFactory(publisher=user, rubric=self.owner)
        self.client.force_login(user)
        for operation in ({}, {"DELETE": "on"}):
            with self.subTest(operation=operation):
                response = self.client.post(
                    self.change_url,
                    self.section_data(
                        [
                            {"id": hidden.pk, "post": own_post.pk, "sort_order": 0, **operation},
                        ],
                        initial=1,
                    ),
                )
                self.assertEqual(response.status_code, 302)
                hidden.refresh_from_db()
                self.assertEqual((hidden.post_id, hidden.sort_order), (self.post.pk, 20))
        self.assert_post_unchanged()

    def test_reordering_visible_placement_preserves_hidden_placements(self):
        hidden = GuideSectionArticle.objects.create(section=self.section, post=self.post, sort_order=20)
        user = self.own_editor()
        own_post = PostFactory(publisher=user, rubric=self.owner)
        visible = GuideSectionArticle.objects.create(section=self.section, post=own_post, sort_order=10)
        self.client.force_login(user)
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"id": visible.pk, "post": own_post.pk, "sort_order": 30},
                ],
                initial=1,
            ),
        )
        self.assertEqual(response.status_code, 302)
        visible.refresh_from_db()
        hidden.refresh_from_db()
        self.assertEqual(visible.sort_order, 30)
        self.assertEqual((hidden.post_id, hidden.sort_order), (self.post.pk, 20))
        self.assert_post_unchanged()

    def test_missing_placement_delete_permission_preserves_existing_placement(self):
        placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.client.force_login(
            self.staff("posts.change_guidesection", "posts.change_guidesectionarticle", "posts.view_post")
        )
        response = self.client.post(
            self.change_url,
            self.section_data(
                [
                    {"id": placement.pk, "post": self.post.pk, "sort_order": 0, "DELETE": "on"},
                ],
                initial=1,
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(GuideSectionArticle.objects.filter(pk=placement.pk).exists())
        self.assert_post_unchanged()

    def test_section_deletion_tree_does_not_disclose_invisible_article_titles(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        user = self.own_editor()
        user.user_permissions.add(Permission.objects.get(codename="delete_guidesection"))
        self.client.force_login(user)
        url = reverse("admin:posts_guidesection_delete", args=[self.section.pk])
        for method, data in ((self.client.get, {}), (self.client.post, {"post": "yes"})):
            response = method(url, data)
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, self.post.title, status_code=403)
        self.assertTrue(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assert_post_unchanged()

    def test_bulk_section_deletion_does_not_disclose_invisible_article_titles(self):
        GuideSectionArticle.objects.create(section=self.section, post=self.post)
        user = self.own_editor()
        user.user_permissions.add(Permission.objects.get(codename="delete_guidesection"))
        self.client.force_login(user)
        url = reverse("admin:posts_guidesection_changelist")
        for confirmation in ({}, {"post": "yes"}):
            response = self.client.post(
                url,
                {
                    "action": "delete_selected",
                    "_selected_action": [self.section.pk],
                    **confirmation,
                },
            )
            self.assertEqual(response.status_code, 403)
            self.assertNotContains(response, self.post.title, status_code=403)
        self.assertTrue(GuideSection.objects.filter(pk=self.section.pk).exists())
        self.assert_post_unchanged()
