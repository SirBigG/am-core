from django.contrib.auth.models import Permission
from django.core.cache import cache
from django.test import override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, PostFactory, StaffUserFactory


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class HubApiTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = StaffUserFactory(is_superuser=True)
        self.authenticate(self.user)
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root, slug="hub-preview")
        self.catalog = CategoryFactory(parent=self.root)
        self.guide = CategoryFactory(parent=self.crop, slug="growing")
        self.post = PostFactory(rubric=self.catalog, title="Existing variety")
        self.post.get_absolute_url()
        self.original_post = Post.objects.values().get(pk=self.post.pk)

    def tearDown(self):
        cache.clear()

    def authenticate(self, user):
        token, _ = Token.objects.get_or_create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def staff(self, *permissions):
        user = StaffUserFactory()
        user.user_permissions.add(*Permission.objects.filter(codename__in=permissions))
        return user

    def create(self, resource, data):
        response = self.client.post(f"/api/content/{resource}/", data, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_crud_configures_crop_and_guide_pages_without_changing_content(self):
        hub = self.create("hubs", {"category": self.crop.pk, "guide_category": self.guide.pk})
        self.assertFalse(hub["is_active"])
        section = self.create(
            "hub-sections",
            {
                "hub": hub["id"],
                "category": self.catalog.pk,
                "role": "varieties",
                "title": "API catalog",
            },
        )
        step = self.create("guide-sections", {"category": self.guide.pk, "title": "Planting", "sort_order": 10})
        placement = self.create("guide-placements", {"section": step["id"], "post": self.post.pk, "sort_order": 5})
        response = self.client.patch(f'/api/content/hubs/{hub["id"]}/', {"is_active": True}, format="json")
        self.assertEqual(response.status_code, 200)
        page = self.client.get("/hub-preview/")
        self.assertContains(page, "API catalog")
        self.assertContains(page, "Planting")
        self.assertEqual(page.context["knowledge_stats"][0]["value"], 1)
        response = self.client.patch(
            f'/api/content/hub-sections/{section["id"]}/', {"title": "Changed label"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(self.client.get("/hub-preview/"), "Changed label")
        for resource, parent, pk in (
            ("hubs", "category", self.crop.pk),
            ("hub-sections", "hub", hub["id"]),
            ("guide-sections", "category", self.guide.pk),
            ("guide-placements", "section", step["id"]),
        ):
            response = self.client.get(f"/api/content/{resource}/", {parent: pk})
            self.assertEqual(response.data["count"], 1)
            self.assertIn("no-store", response["Cache-Control"])
        original_category = Category.objects.values().get(pk=self.guide.pk)
        response = self.client.patch(
            f"/api/content/categories/{self.guide.pk}/presentation/",
            {
                "presentation_mode": "guide_hub",
                "slug": "do-not-rewrite",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        original_category["presentation_mode"] = "guide_hub"
        self.assertEqual(Category.objects.values().get(pk=self.guide.pk), original_category)
        self.assertContains(self.client.get(self.guide.get_absolute_url()), "Planting")
        self.assertEqual(
            self.client.patch(
                f'/api/content/guide-placements/{placement["id"]}/', {"sort_order": 2}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/content/guide-sections/{step["id"]}/', {"title": "Updated step"}, format="json"
            ).status_code,
            200,
        )
        self.assertContains(self.client.get("/hub-preview/"), "Updated step")
        self.assertEqual(self.client.delete(f'/api/content/guide-placements/{placement["id"]}/').status_code, 204)
        self.assertEqual(self.client.get("/hub-preview/").context["growing_guides"], [])
        self.assertEqual(self.client.delete(f'/api/content/guide-sections/{step["id"]}/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/content/hub-sections/{section["id"]}/').status_code, 204)
        self.assertEqual(self.client.delete(f'/api/content/hubs/{hub["id"]}/').status_code, 204)
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_market_widget_category_is_writable_nullable_and_permission_scoped(self):
        hub = self.create("hubs", {"category": self.crop.pk, "market_category": self.catalog.pk})
        url = f'/api/content/hubs/{hub["id"]}/'
        self.assertEqual(hub["market_category"], self.catalog.pk)
        self.assertEqual(self.client.get(url).data["market_category"], self.catalog.pk)
        reader = self.staff("view_categoryhub")
        self.authenticate(reader)
        self.assertEqual(self.client.patch(url, {"market_category": self.guide.pk}, format="json").status_code, 403)
        self.authenticate(self.user)
        response = self.client.patch(url, {"market_category": self.guide.pk}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["market_category"], self.guide.pk)
        self.assertEqual(self.client.patch(url, {"market_category": 999999}, format="json").status_code, 400)
        response = self.client.patch(url, {"market_category": None}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["market_category"])
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_token_only_staff_and_action_specific_permissions(self):
        urls = [
            f"/api/content/{resource}/" for resource in ("hubs", "hub-sections", "guide-sections", "guide-placements")
        ]
        urls.append(f"/api/content/categories/{self.guide.pk}/presentation/")
        self.client.credentials()
        self.client.force_login(self.user)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)
        ordinary = StaffUserFactory(is_staff=False)
        self.authenticate(ordinary)
        self.assertEqual(self.client.get(urls[0]).status_code, 403)
        no_permissions = StaffUserFactory()
        self.authenticate(no_permissions)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
        reader = self.staff("view_categoryhub")
        self.authenticate(reader)
        self.assertEqual(self.client.get(urls[0]).status_code, 200)
        self.assertEqual(self.client.post(urls[0], {"category": self.crop.pk}).status_code, 403)
        editor = self.staff("change_category")
        self.authenticate(editor)
        self.assertEqual(self.client.patch(urls[-1], {"presentation_mode": "guide_hub"}).status_code, 200)
        self.assertEqual(
            self.client.post(urls[2], {"category": self.guide.pk, "title": "Not permitted"}).status_code, 403
        )

    def test_model_constraints_partial_updates_and_bad_filters_return_400(self):
        hub = self.create("hubs", {"category": self.crop.pk})
        section = self.create("hub-sections", {"hub": hub["id"], "category": self.catalog.pk, "role": "varieties"})
        for data in (
            {"hub": hub["id"], "category": self.guide.pk, "role": "varieties"},
            {"hub": hub["id"], "category": self.catalog.pk, "role": "diseases"},
            {"hub": hub["id"], "category": self.crop.pk, "role": "growing"},
            {"hub": hub["id"], "category": self.root.pk, "role": "growing"},
        ):
            response = self.client.post("/api/content/hub-sections/", data, format="json")
            self.assertEqual(response.status_code, 400, response.data)
        self.assertEqual(
            self.client.patch(
                f'/api/content/hubs/{hub["id"]}/', {"locale": "not-a-language"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f'/api/content/hubs/{hub["id"]}/', {"category": self.catalog.pk}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(self.client.get("/api/content/hub-sections/?hub=not-a-number").status_code, 400)
        self.assertEqual(
            self.client.patch(
                f'/api/content/hub-sections/{section["id"]}/', {"is_active": False}, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/content/categories/{self.guide.pk}/presentation/",
                {"presentation_mode": "invalid"},
                format="json",
            ).status_code,
            400,
        )
        self.assertEqual(CategoryHubSection.objects.count(), 1)

    def test_hidden_post_placements_stay_private_and_cascades_are_protected(self):
        own = PostFactory(rubric=self.catalog)
        section = GuideSection.objects.create(category=self.guide, title="Step")
        hidden = GuideSectionArticle.objects.create(section=section, post=self.post)
        editor = self.staff(
            "view_guidesectionarticle",
            "add_guidesectionarticle",
            "change_guidesectionarticle",
            "delete_guidesectionarticle",
            "delete_guidesection",
            "change_own_post",
        )
        Post.objects.filter(pk=own.pk).update(publisher=editor)
        own_placement = GuideSectionArticle.objects.create(section=section, post=own)
        self.authenticate(editor)
        response = self.client.get("/api/content/guide-placements/")
        self.assertEqual([row["id"] for row in response.data["results"]], [own_placement.pk])
        self.assertEqual(self.client.get(f"/api/content/guide-placements/{hidden.pk}/").status_code, 404)
        self.assertEqual(
            self.client.patch(f"/api/content/guide-placements/{hidden.pk}/", {"sort_order": 20}).status_code, 404
        )
        self.assertEqual(self.client.delete(f"/api/content/guide-placements/{hidden.pk}/").status_code, 404)
        self.assertEqual(
            self.client.post(
                "/api/content/guide-placements/", {"section": section.pk, "post": self.post.pk}
            ).status_code,
            400,
        )
        self.assertEqual(self.client.delete(f"/api/content/guide-sections/{section.pk}/").status_code, 403)
        self.assertTrue(GuideSection.objects.filter(pk=section.pk).exists())
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)

    def test_populated_hub_and_guide_need_child_delete_permission(self):
        hub = CategoryHub.objects.create(category=self.crop)
        CategoryHubSection.objects.create(hub=hub, category=self.catalog, role="varieties")
        section = GuideSection.objects.create(category=self.guide, title="Step")
        GuideSectionArticle.objects.create(section=section, post=self.post)
        editor = self.staff("delete_categoryhub", "delete_guidesection", "view_post")
        self.authenticate(editor)
        self.assertEqual(self.client.delete(f"/api/content/hubs/{hub.pk}/").status_code, 403)
        self.assertEqual(self.client.delete(f"/api/content/guide-sections/{section.pk}/").status_code, 403)
        self.assertTrue(CategoryHub.objects.filter(pk=hub.pk).exists())
        self.assertTrue(GuideSection.objects.filter(pk=section.pk).exists())

    def test_duplicate_placements_rejected_without_duplicate_posts(self):
        section = self.create("guide-sections", {"category": self.guide.pk, "title": "Step"})
        self.create("guide-placements", {"section": section["id"], "post": self.post.pk})
        response = self.client.post("/api/content/guide-placements/", {"section": section["id"], "post": self.post.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(GuideSectionArticle.objects.count(), 1)
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), self.original_post)
