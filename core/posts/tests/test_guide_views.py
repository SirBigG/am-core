import json
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from lxml import html

from core.classifier.models import Category, CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, MetaDataFactory, PostFactory


@override_settings(HOST="https://agromega.in.ua")
class GuideHubViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root, slug="kartoplya")
        self.hub = CategoryFactory(
            parent=self.crop,
            slug="vyroshchuvannya",
            value="Вирощування картоплі",
            presentation_mode=CategoryPresentationMode.GUIDE_HUB,
        )
        self.owner = CategoryFactory(parent=self.crop, slug="other-articles")
        self.post = PostFactory(rubric=self.owner, title="Preparing seed potatoes", text="Original article body")
        self.post_url = self.post.get_absolute_url()
        self.section = GuideSection.objects.create(category=self.hub, title="Planting", description="Practical steps")
        self.placement = GuideSectionArticle.objects.create(section=self.section, post=self.post)
        self.url = reverse("posts-list-view", kwargs={"parent": self.crop.slug, "child": self.hub.slug})
        self.list_url = reverse("posts-list-child", kwargs={"parent": self.crop.slug, "child": self.hub.slug})

    def document(self, response):
        return html.fromstring(response.content)

    def collection_data(self, response):
        return next(
            data
            for text in self.document(response).xpath('//script[@type="application/ld+json"]/text()')
            if (data := json.loads(text)).get("@type") == "CollectionPage"
        )

    def test_existing_category_route_renders_guide_with_original_article_links(self):
        original = Post.objects.values().get(pk=self.post.pk)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "posts/guide_hub.html")
        self.assertContains(response, f'href="{self.post_url}"')
        self.assertContains(response, "Practical steps")
        self.assertNotContains(response, "Original article body")
        self.assertNotContains(response, 'id="category-filters"')
        self.assertNotContains(response, "Алфавітний каталог")
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), original)
        detail = self.client.get(self.post_url)
        self.assertEqual(detail.status_code, 200)
        self.assertTemplateUsed(detail, "posts/detail.html")

    def test_guide_does_not_execute_catalog_filter_queries(self):
        with (
            patch("core.posts.views.build_category_attribute_filters", side_effect=AssertionError("catalog filters")),
            patch("core.posts.views.PostListView._get_post_countries", side_effect=AssertionError("countries")),
        ):
            response = self.client.get(self.url, {"country": "unknown", "order": "title"})
        self.assertContains(response, self.post.title)

    def test_section_and_placement_orders_and_repeated_article_references(self):
        self.section.sort_order = 10
        self.section.save()
        earlier = GuideSection.objects.create(category=self.hub, title="Planning", sort_order=0)
        tied = GuideSection.objects.create(category=self.hub, title="Storage", sort_order=10)
        for section in (earlier, tied):
            GuideSectionArticle.objects.create(section=section, post=self.post)
        self.placement.sort_order = 20
        self.placement.save()
        first = PostFactory(rubric=self.owner, title="First ordered article")
        second = PostFactory(rubric=self.owner, title="Second ordered article")
        for post in (first, second):
            post.get_absolute_url()
            GuideSectionArticle.objects.create(section=self.section, post=post, sort_order=10)
        response = self.client.get(self.url)
        document = self.document(response)
        self.assertEqual(document.xpath("//section[@aria-labelledby]/h2/text()"), ["Planning", "Planting", "Storage"])
        links = document.xpath(f'//section[@id="section-{self.section.pk}"]//ol/li/a/@href')
        self.assertEqual(links, [first.absolute_url, second.absolute_url, self.post_url])
        self.assertEqual(len(document.xpath(f'//section//a[@href="{self.post_url}"]')), 3)
        self.assertEqual(response.context["post_count"], 3)
        self.assertEqual(self.collection_data(response)["mainEntity"]["numberOfItems"], 3)

    def test_inactive_sections_articles_and_owner_categories_are_not_rendered(self):
        hidden_section = GuideSection.objects.create(category=self.hub, title="Hidden section", is_active=False)
        GuideSectionArticle.objects.create(section=hidden_section, post=self.post)
        empty = GuideSection.objects.create(category=self.hub, title="Only hidden articles")
        inactive_post = PostFactory(rubric=self.owner, title="Hidden post", status=False)
        GuideSectionArticle.objects.create(section=empty, post=inactive_post)
        inactive_category = CategoryFactory(parent=self.crop, value="Hidden category", is_active=False)
        hidden_post = PostFactory(rubric=inactive_category, title="Hidden category article")
        GuideSectionArticle.objects.create(section=self.section, post=hidden_post)
        inactive_root = CategoryFactory(is_active=False)
        hidden_owner = CategoryFactory(parent=CategoryFactory(parent=inactive_root))
        hidden_descendant_post = PostFactory(rubric=hidden_owner, title="Hidden ancestor article")
        GuideSectionArticle.objects.create(section=self.section, post=hidden_descendant_post)
        response = self.client.get(self.url)
        for title in (
            hidden_section.title,
            empty.title,
            inactive_post.title,
            inactive_category.value,
            hidden_post.title,
            hidden_descendant_post.title,
        ):
            self.assertNotContains(response, title)
        self.assertContains(response, self.post.title)
        self.assertEqual(self.collection_data(response)["mainEntity"]["numberOfItems"], 1)

    def test_inactive_hub_or_ancestor_returns_404_in_both_category_routes(self):
        for category in (self.hub, self.crop, self.root):
            with self.subTest(category=category.pk):
                Category.objects.filter(pk=category.pk).update(is_active=False)
                self.assertEqual(self.client.get(self.url).status_code, 404)
                self.assertEqual(self.client.get(self.list_url).status_code, 404)
                Category.objects.filter(pk=category.pk).update(is_active=True)

    def test_wrong_parent_and_missing_category_return_404(self):
        self.assertEqual(self.client.get(f"/wrong-parent/{self.hub.slug}/").status_code, 404)
        self.assertEqual(self.client.get(f"/wrong-parent/{self.hub.slug}/list/").status_code, 404)
        self.assertEqual(self.client.get(f"/{self.crop.slug}/missing/").status_code, 404)

    def test_empty_guide_has_an_explicit_empty_state(self):
        Post.objects.filter(pk=self.post.pk).update(status=False)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Матеріали посібника готуються до публікації.")
        self.assertNotContains(response, 'aria-label="Розділи посібника"')
        self.assertEqual(self.collection_data(response)["mainEntity"]["numberOfItems"], 0)

    def test_metadata_canonical_and_breadcrumbs_use_hub_identity(self):
        self.hub.meta = MetaDataFactory(
            title="Potato guide SEO",
            h1="Growing potatoes",
            description="Practical potato guide",
            text="<p>Guide introduction</p>",
        )
        self.hub.save()
        response = self.client.get(self.url)
        document = self.document(response)
        self.assertEqual(document.xpath("string(//title)").strip(), "Potato guide SEO")
        self.assertEqual(document.xpath("string(//h1)").strip(), "Growing potatoes")
        self.assertEqual(document.xpath('//meta[@name="description"]/@content'), ["Practical potato guide"])
        canonical = "https://agromega.in.ua" + self.url
        self.assertEqual(document.xpath('//link[@rel="canonical"]/@href'), [canonical])
        self.assertEqual(document.xpath('//meta[@property="og:url"]/@content'), [canonical])
        self.assertContains(response, "Guide introduction")
        self.assertContains(response, self.hub.value)
        data = self.collection_data(response)
        self.assertEqual(data["url"], canonical)
        self.assertEqual(data["mainEntity"]["itemListElement"][0]["url"], "https://agromega.in.ua" + self.post_url)

    def test_plain_section_fields_are_escaped_and_anchor_identity_survives_rename(self):
        self.section.title = '<script>alert("section")</script>'
        self.section.description = '<img src=x onerror="alert(1)">'
        self.section.save()
        response = self.client.get(self.url)
        self.assertNotContains(response, self.section.title)
        self.assertNotContains(response, self.section.description)
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, f'href="#section-{self.section.pk}"')
        self.assertContains(response, f'id="section-{self.section.pk}"')

    def test_missing_article_url_is_not_generated_or_saved_during_render(self):
        Post.objects.filter(pk=self.post.pk).update(absolute_url="")
        original = Post.objects.values().get(pk=self.post.pk)
        response = self.client.get(self.url)
        self.assertContains(response, self.post.title)
        self.assertNotContains(response, 'href=""')
        self.assertEqual(self.collection_data(response)["mainEntity"]["numberOfItems"], 0)
        self.assertEqual(Post.objects.values().get(pk=self.post.pk), original)

    def test_guide_list_alias_redirects_to_category_for_get_and_head(self):
        for method in (self.client.get, self.client.head):
            response = method(self.list_url + "?page=2")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], self.url)
            self.assertIn("no-store", response.headers["Cache-Control"])

    def test_switching_back_to_catalog_preserves_existing_catalog_and_pagination(self):
        catalog_post = PostFactory(rubric=self.hub, title="Catalog article")
        catalog_post.get_absolute_url()
        Category.objects.filter(pk=self.hub.pk).update(presentation_mode=CategoryPresentationMode.CATALOG)
        with patch("core.posts.views.get_public_guide_sections", side_effect=AssertionError("guide query")):
            response = self.client.get(self.url)
            self.assertTemplateUsed(response, "posts/list_order.html")
            self.assertContains(response, 'id="category-filters"')
            self.assertContains(response, catalog_post.title)
            self.assertNotContains(response, self.post.title)
            response = self.client.get(self.list_url)
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "posts/list.html")
            self.assertEqual(response.context["paginator"].per_page, 50)

    def test_full_page_batches_guide_queries_as_sections_grow(self):
        def guide_query_count():
            with CaptureQueriesContext(connection) as queries:
                response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            return sum(
                'FROM "guide_section"' in query["sql"] or 'FROM "guide_section_article"' in query["sql"]
                for query in queries
            )

        self.assertEqual(guide_query_count(), 2)
        for index in range(8):
            section = GuideSection.objects.create(category=self.hub, title=f"Stage {index}")
            GuideSectionArticle.objects.create(section=section, post=self.post)
        self.assertEqual(guide_query_count(), 2)
