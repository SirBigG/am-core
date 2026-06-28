from django.test import Client, RequestFactory, TestCase

from core.posts.category_attributes import rebuild_post_attribute_values
from core.posts.models import CategoryAttributeFieldType, SearchStatistic
from core.utils.tests.factories import (
    CategoryAttributeChoiceFactory,
    CategoryAttributeFieldFactory,
    CategoryAttributeGroupFactory,
    CategoryFactory,
    PhotoFactory,
    PostFactory,
)

client = Client()

request = RequestFactory()


class MainPageTest(TestCase):

    def test_response(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(3, rubric=rubric)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("object_list", response.context)
        self.assertTemplateUsed(response, "index.html")

    def test_active_status_filter(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(2, rubric=rubric)
        PostFactory.create_batch(2, status=0, rubric=rubric)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["object_list"].count(), 2)

    def test_service_worker_served_from_current_origin(self):
        response = self.client.get("/service-worker.js")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["Content-Type"], "application/javascript")
        self.assertEqual(response.headers["Cache-Control"], "no-cache")

    def test_plant_diary_landing(self):
        response = self.client.get("/plant-diary")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "plant_diary.html")


class PostListTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_parent_list(self):
        response = client.get("/%s/" % self.parent.slug)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/parent_index.html")
        self.assertEqual(response.context["category"], self.parent)
        self.assertEqual(len(response.context["object_list"]), 1)

    def test_parent_list_404(self):
        response = client.get("/unknown/")
        self.assertEqual(response.status_code, 404)

    def test_child_list_grouped(self):
        slug = self.post.rubric.slug
        response = client.get(f"/{self.parent.slug}/{slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/list_order.html")
        self.assertFalse(response.context["has_active_filters"])
        self.assertContains(response, 'id="category-filters"', html=False)
        self.assertContains(response, "<details", html=False)

    def test_child_list_grouped_opens_filter_panel_when_filter_is_active(self):
        slug = self.post.rubric.slug
        response = client.get(f"/{self.parent.slug}/{slug}/", {"country": "ukraine"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["has_active_filters"])
        self.assertContains(response, 'id="category-filters"', html=False)
        self.assertContains(response, '<details class="site-content-section" open>', html=False)

    def test_child_list(self):
        slug = self.post.rubric.slug
        response = client.get(f"/{self.parent.slug}/{slug}/list/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/list.html")
        self.assertEqual(len(response.context["object_list"]), 1)
        PostFactory(rubric=self.post.rubric)
        PostFactory(rubric=self.post.rubric)
        response = client.get(f"/{self.parent.slug}/{slug}/list/")
        self.assertEqual(len(response.context["object_list"]), 3)
        self.assertEqual(response.context["category"], self.post.rubric)

    def test_child_list_404(self):
        response = client.get("/%s/unknown/" % self.parent.slug)
        self.assertEqual(response.status_code, 404)

    def test_child_list_grouped_includes_public_attribute_filters(self):
        field = CategoryAttributeFieldFactory(category=self.category, key="ripening", label="Ripening")
        winter = CategoryAttributeChoiceFactory(field=field, value="winter", label="Winter")
        summer = CategoryAttributeChoiceFactory(field=field, value="summer", label="Summer")
        self.post.category_attributes = {str(self.category.pk): {"ripening": winter.value}}
        self.post.save()
        rebuild_post_attribute_values(self.post)
        summer_post = PostFactory(
            rubric=self.category,
            title="Summer post",
            category_attributes={str(self.category.pk): {"ripening": summer.value}},
        )
        rebuild_post_attribute_values(summer_post)

        response = client.get(f"/{self.parent.slug}/{self.category.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["attribute_filters"][0]["key"], "ripening")
        self.assertEqual(len(response.context["attribute_filters"][0]["options"]), 2)

    def test_child_list_grouped_filters_by_public_attribute(self):
        field = CategoryAttributeFieldFactory(category=self.category, key="ripening")
        winter = CategoryAttributeChoiceFactory(field=field, value="winter", label="Winter")
        summer = CategoryAttributeChoiceFactory(field=field, value="summer", label="Summer")
        self.post.category_attributes = {str(self.category.pk): {"ripening": winter.value}}
        self.post.save()
        rebuild_post_attribute_values(self.post)
        summer_post = PostFactory(
            rubric=self.category,
            category_attributes={str(self.category.pk): {"ripening": summer.value}},
        )
        rebuild_post_attribute_values(summer_post)

        response = client.get(f"/{self.parent.slug}/{self.category.slug}/", {"attr_ripening": "winter"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["post_count"], 1)

    def test_child_list_grouped_excludes_internal_attribute_filters(self):
        field = CategoryAttributeFieldFactory(category=self.category, key="internal", is_public=False)
        choice = CategoryAttributeChoiceFactory(field=field, value="yes", label="Yes")
        self.post.category_attributes = {str(self.category.pk): {"internal": choice.value}}
        self.post.save()
        rebuild_post_attribute_values(self.post)

        response = client.get(f"/{self.parent.slug}/{self.category.slug}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["attribute_filters"], [])

    def test_child_paginated_list_does_not_include_attribute_filters_yet(self):
        CategoryAttributeFieldFactory(
            category=self.category,
            key="fruit_weight",
            field_type=CategoryAttributeFieldType.RANGE,
        )
        self.post.category_attributes = {str(self.category.pk): {"fruit_weight": {"min": "100", "max": "150"}}}
        self.post.save()
        rebuild_post_attribute_values(self.post)

        response = client.get(f"/{self.parent.slug}/{self.category.slug}/list/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("attribute_filters", response.context)


class PostDetailTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        child = CategoryFactory(parent=self.parent)
        self.category = CategoryFactory(parent=child)
        self.post = PostFactory(rubric=self.category)

    def test_detail(self):
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/detail.html")
        self.assertIn("object", response.context)
        self.assertEqual(len(response.context["menu_items"]), 1)

    def test_detail_does_not_show_add_photo_link(self):
        PhotoFactory(post=self.post)
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/gallery/add/")
        self.assertNotContains(response, "Додати фото до публікації")

    def test_detail_renders_sources_as_rich_text(self):
        self.post.sources = "<p><strong>Джерело:</strong> довідник садівника</p>"
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>Джерело:</strong>", html=False)

    def test_detail_renders_public_category_attributes(self):
        group = CategoryAttributeGroupFactory(category=self.category, title="Плоди")
        field = CategoryAttributeFieldFactory(category=self.category, group=group, key="fruit_size", label="Розмір")
        choice = CategoryAttributeChoiceFactory(field=field, value="large", label="Великий")
        self.post.category_attributes = {str(self.category.pk): {"fruit_size": choice.value}}
        self.post.save()
        rebuild_post_attribute_values(self.post)

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Характеристики")
        self.assertContains(response, "Плоди")
        self.assertContains(response, "Розмір")
        self.assertContains(response, "Великий")

    def test_detail_hides_internal_category_attributes(self):
        field = CategoryAttributeFieldFactory(
            category=self.category,
            key="internal_note",
            label="Internal note",
            is_public=False,
        )
        choice = CategoryAttributeChoiceFactory(field=field, value="hidden", label="Hidden")
        self.post.category_attributes = {str(self.category.pk): {"internal_note": choice.value}}
        self.post.save()
        rebuild_post_attribute_values(self.post)

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Internal note")
        self.assertNotContains(response, "Hidden")


class GalleryTests(TestCase):

    def setUp(self):
        self.parent = CategoryFactory()
        self.category = CategoryFactory(parent=self.parent)
        self.post = PostFactory(rubric=self.category)

    def test_gallery_does_not_show_add_photo_link(self):
        PhotoFactory(post=self.post)
        response = client.get("/gallery/%s/" % self.post.id)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/gallery/add/")
        self.assertNotContains(response, "Завантажити фото публікації")

    def test_gallery_add_photo_url_is_not_available(self):
        response = client.get("/gallery/add/%s/" % self.post.id)
        self.assertEqual(response.status_code, 404)


class PostSearchTests(TestCase):
    def test_search_page_renders_without_query(self):
        response = self.client.get("/search/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/search.html")
        self.assertEqual(SearchStatistic.objects.count(), 0)

    def test_search_query_renders_no_results_and_records_statistic(self):
        response = self.client.get("/search/", {"q": "missing query"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/search.html")
        self.assertEqual(SearchStatistic.objects.count(), 1)
        self.assertEqual(SearchStatistic.objects.get().search_phrase, "missing query")


class SiteMapTests(TestCase):
    def setUp(self):
        root = CategoryFactory()
        parent = CategoryFactory(parent=root)
        child = CategoryFactory(parent=parent)
        PostFactory.create_batch(5, **{"rubric": child})

    def test_return_context(self):
        response = client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["urls"]), 3)
        self.assertTemplateUsed(response, "sitemap_index.xml")


class ErrorsHandlerTests(TestCase):

    def test_404_handler_using(self):
        response = client.get("/sdg/sdg/dfdg")
        self.assertTemplateUsed(response, "404.html")
        self.assertTemplateUsed(response, "header.html")
        self.assertTemplateUsed(response, "footer.html")

    # TODO: create test for 500 handler
