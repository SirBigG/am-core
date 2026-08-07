import json
import re

from django.core.cache import cache
from django.db import connection
from django.test import Client, RequestFactory, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.posts.category_attributes import rebuild_post_attribute_values
from core.posts.models import CategoryAttributeFieldType, SearchStatistic
from core.utils.tests.factories import (
    CategoryAttributeChoiceFactory,
    CategoryAttributeFieldFactory,
    CategoryAttributeGroupFactory,
    CategoryFactory,
    MetaDataFactory,
    PhotoFactory,
    PostFactory,
    UserFactory,
)

client = Client()

request = RequestFactory()


class RandomPostRecommendationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.posts = []
        for index in range(10):
            root = CategoryFactory(value=f"Root {index}")
            rubric = CategoryFactory(parent=root, value=f"Rubric {index}")
            post = PostFactory(rubric=rubric, title=f"Recommendation {index}")
            PhotoFactory(post=post)
            self.posts.append(post)
        self.url = reverse("random-post-recommendations")

    def test_fragment_returns_four_unique_imaged_posts_from_different_trees(self):
        no_photo = PostFactory(title="No photo")
        inactive = PostFactory(title="Inactive", status=False)
        PhotoFactory(post=inactive)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(
                self.url,
                {"current": self.posts[0].pk},
                headers={"hx-request": "true"},
            )

        recommendations = response.context["posts"]
        recommendation_ids = [post.pk for post in recommendations]
        tree_ids = [post.rubric.tree_id for post in recommendations]
        sql = " ".join(query["sql"] for query in queries)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/random_posts.html")
        self.assertEqual(len(recommendations), 4)
        self.assertEqual(len(set(recommendation_ids)), 4)
        self.assertEqual(len(set(tree_ids)), 4)
        self.assertNotIn(self.posts[0].pk, recommendation_ids)
        self.assertNotIn(no_photo.pk, recommendation_ids)
        self.assertNotIn(inactive.pk, recommendation_ids)
        self.assertNotIn("RANDOM()", sql.upper())
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertContains(response, "Інші варіанти")
        self.assertNotContains(response, 'aria-label="Показати інші випадкові публікації"', html=False)

    def test_refresh_excludes_the_currently_visible_recommendations(self):
        first_response = self.client.get(
            self.url,
            {"current": self.posts[0].pk},
            headers={"hx-request": "true"},
        )
        first_ids = {post.pk for post in first_response.context["posts"]}

        second_response = self.client.get(
            first_response.context["refresh_url"],
            headers={"hx-request": "true"},
        )
        second_ids = {post.pk for post in second_response.context["posts"]}

        self.assertEqual(len(second_ids), 4)
        self.assertTrue(first_ids.isdisjoint(second_ids))
        self.assertNotIn(self.posts[0].pk, second_ids)
        self.assertContains(second_response, 'hx-swap="outerHTML"', html=False)

    def test_exclusion_parser_is_bounded_and_ignores_invalid_values(self):
        excluded = [post.pk for post in self.posts[1:5]]

        response = self.client.get(
            self.url,
            {
                "current": f"invalid,{self.posts[0].pk}",
                "exclude": f"invalid,-1,{','.join(str(post_id) for post_id in excluded)}",
            },
            headers={"hx-request": "true"},
        )
        recommendation_ids = {post.pk for post in response.context["posts"]}

        self.assertNotIn(self.posts[0].pk, recommendation_ids)
        self.assertTrue(recommendation_ids.isdisjoint(excluded))


class MainPageTest(TestCase):

    def test_response(self):
        parent = CategoryFactory()
        rubric = CategoryFactory(parent=parent)
        PostFactory.create_batch(3, rubric=rubric)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("object_list", response.context)
        self.assertTemplateUsed(response, "index.html")

    @override_settings(HOST="https://agromega.in.ua")
    def test_homepage_has_trailing_slash_canonical(self):
        response = self.client.get("/")

        self.assertContains(response, '<link rel="canonical" href="https://agromega.in.ua/">', html=True)
        self.assertContains(response, '<meta name="robots" content="index,follow">', html=True)
        self.assertContains(response, '<meta content="https://agromega.in.ua/" property="og:url">', html=True)
        self.assertContains(
            response,
            '<meta content="https://agromega.in.ua/static/posts/og-default.png" property="og:image">',
            html=True,
        )
        payloads = re.findall(rb'<script type="application/ld\+json">(.*?)</script>', response.content, flags=re.DOTALL)
        structured_data = [json.loads(payload) for payload in payloads]
        site_graph = next(data["@graph"] for data in structured_data if "@graph" in data)
        self.assertEqual([item["@type"] for item in site_graph], ["Organization", "WebSite"])
        self.assertEqual(site_graph[1]["potentialAction"]["@type"], "SearchAction")

    @override_settings(HOST="https://agromega.in.ua")
    def test_query_variant_is_noindex_and_canonicalizes_to_path(self):
        response = self.client.get("/", {"page": "2"})

        self.assertContains(response, '<link rel="canonical" href="https://agromega.in.ua/">', html=True)
        self.assertContains(response, '<meta name="robots" content="noindex,follow">', html=True)

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
        content = b"".join(response.streaming_content).decode()
        self.assertIn('const AGROMEGA_CACHE_VERSION = "agromega-v2";', content)
        self.assertIn('const NETWORK_FIRST_DESTINATIONS = new Set(["script", "style"]);', content)

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
        self.assertContains(response, '<details class="site-content-section"', html=False)
        self.assertContains(response, "open", html=False)

    def test_child_list_grouped_caches_countries_per_category(self):
        other_category = CategoryFactory(parent=self.parent)
        PostFactory(rubric=other_category)

        cache.clear()
        client.get(f"/{self.parent.slug}/{self.category.slug}/")
        client.get(f"/{self.parent.slug}/{other_category.slug}/")

        self.assertIsNotNone(cache.get(f"post_countries_{self.category.pk}"))
        self.assertIsNotNone(cache.get(f"post_countries_{other_category.pk}"))

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

    def test_child_list_prefetches_primary_photos_without_n_plus_one_queries(self):
        posts = [self.post, *PostFactory.create_batch(5, rubric=self.category)]
        for post in posts:
            PhotoFactory(post=post)

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(f"/{self.parent.slug}/{self.category.slug}/list/")

        photo_queries = [query["sql"] for query in queries if 'FROM "photo"' in query["sql"]]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(photo_queries), 1)

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

    def test_detail_uses_page_h1_for_article_heading(self):
        self.post.page_h1 = "Повний H1 сторінки публікації"
        self.post.meta = MetaDataFactory(h1="Старий metadata H1")
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Повний H1 сторінки публікації")
        self.assertNotContains(response, "Старий metadata H1")

    def test_detail_ignores_metadata_h1_and_falls_back_to_title(self):
        self.post.title = "Назва у списках"
        self.post.meta = MetaDataFactory(h1="Metadata H1")
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Назва у списках")
        self.assertNotContains(response, "Metadata H1")

    def test_detail_does_not_show_add_photo_link(self):
        PhotoFactory(post=self.post)
        response = client.get(self.post.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "/gallery/add/")
        self.assertNotContains(response, "Додати фото до публікації")

    def test_detail_loads_random_recommendations_asynchronously(self):
        response = self.client.get(self.post.get_absolute_url())

        recommendations_url = reverse("random-post-recommendations")
        self.assertContains(response, f'hx-get="{recommendations_url}?current={self.post.pk}"', html=False)
        self.assertContains(response, 'hx-trigger="load"', html=False)
        self.assertContains(response, "posts/htmx.min.js", html=False)

    def test_detail_defers_javascript_without_loading_fontawesome(self):
        response = self.client.get(self.post.get_absolute_url())

        self.assertContains(response, 'src="/static/posts/j-detail.js" defer', html=False)
        self.assertNotContains(response, "posts/fontawesome/css/all.min.css", html=False)

    def test_authenticated_detail_omits_unused_fontawesome_and_names_profile_menu(self):
        self.client.force_login(UserFactory())

        response = self.client.get(self.post.get_absolute_url())

        self.assertNotContains(response, "posts/fontawesome/css/all.min.css", html=False)
        self.assertContains(response, 'aria-label="Відкрити меню профілю"', html=False)
        self.assertContains(response, 'class="site-footer__heading text-uppercase h5"', html=False)

    def test_detail_prefetches_photos_once(self):
        PhotoFactory.create_batch(3, post=self.post)
        self.client.get(self.post.get_absolute_url())

        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(self.post.get_absolute_url())

        photo_queries = [query["sql"] for query in queries if 'FROM "photo"' in query["sql"]]
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(photo_queries), 1)

    def test_detail_renders_sources_as_rich_text(self):
        self.post.sources = "<p><strong>Джерело:</strong> довідник садівника</p>"
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<strong>Джерело:</strong>", html=False)

    def test_detail_renders_faq_structured_data_for_visible_faq_blocks(self):
        self.post.text = """
            <p>Article introduction.</p>
            <div class="article-faq-item">
                <p>Чи є це питанням?</p>
                <p>Так, це видима відповідь.</p>
            </div>
        """
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        payloads = re.findall(rb'<script type="application/ld\+json">(.*?)</script>', response.content)
        structured_data = [json.loads(payload) for payload in payloads]
        faq_data = next(data for data in structured_data if data.get("@type") == "FAQPage")
        self.assertEqual(faq_data["mainEntity"][0]["name"], "Чи є це питанням?")
        self.assertEqual(
            faq_data["mainEntity"][0]["acceptedAnswer"]["text"],
            "Так, це видима відповідь.",
        )

    def test_detail_omits_faq_structured_data_without_complete_faq_blocks(self):
        self.post.text = '<div class="article-faq-item"><p>Question without an answer?</p></div>'
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        payloads = re.findall(rb'<script type="application/ld\+json">(.*?)</script>', response.content)
        structured_data = [json.loads(payload) for payload in payloads]
        self.assertNotIn("FAQPage", {data.get("@type") for data in structured_data})

    def test_detail_prefers_post_meta_description(self):
        self.post.meta_description = "Purpose-written search description."
        self.post.text = "<p>Article text that should not become the description.</p>"
        self.post.save()

        response = client.get(self.post.get_absolute_url())

        head = response.content.split(b"</head>", 1)[0]
        self.assertIn(b'<meta name="description"', head)
        self.assertIn(b"Purpose-written search description.", head)
        self.assertNotIn(b"Article text that should not become the description.", head)

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
        self.assertContains(response, '<meta name="robots" content="noindex,follow">', html=True)

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
        self.assertEqual(len(response.context["urls"]), 4)
        self.assertTemplateUsed(response, "sitemap_index.xml")

    @override_settings(FORUM_BASE_URL="https://agromega.in.ua/community/")
    def test_index_includes_normalized_forum_owned_sitemap(self):
        response = client.get("/sitemap.xml")

        self.assertContains(response, "<loc>https://agromega.in.ua/community/sitemap.xml</loc>", html=False)
        self.assertNotContains(response, "/community//sitemap.xml", html=False)

    @override_settings(HOST="https://agromega.in.ua/")
    def test_index_normalizes_host_and_renders_available_lastmod(self):
        response = client.get("/sitemap.xml")

        self.assertContains(response, "<loc>https://agromega.in.ua/sitemap-main.xml</loc>", html=False)
        self.assertContains(response, "<lastmod>", html=False)
        self.assertNotContains(response, "https://agromega.in.ua//sitemap", html=False)

    def test_index_handles_no_published_posts(self):
        from core.posts.models import Post

        Post.objects.update(status=False)

        response = client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        main_sitemap = next(url for url in response.context["urls"] if url["loc"].endswith("sitemap-main.xml"))
        self.assertIsNone(main_sitemap["lastmod"])

    @override_settings(HOST="https://agromega.in.ua")
    def test_main_sitemap_has_unique_urls_and_one_slash_homepage(self):
        response = client.get("/sitemap-main.xml")
        locations = [url["loc"] for url in response.context["urls"]]

        self.assertEqual(locations.count("https://agromega.in.ua/"), 1)
        self.assertEqual(len(locations), len(set(locations)))


class ErrorsHandlerTests(TestCase):

    def test_404_handler_using(self):
        response = client.get("/sdg/sdg/dfdg")
        self.assertTemplateUsed(response, "404.html")
        self.assertTemplateUsed(response, "header.html")
        self.assertTemplateUsed(response, "footer.html")

    # TODO: create test for 500 handler
