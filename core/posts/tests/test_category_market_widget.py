from datetime import timedelta

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.companies.market import market_offers
from core.companies.models import Company, Product
from core.posts.crop_hub import build_crop_hub_context, hub_config
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, LocationFactory, PostFactory


@override_settings(
    HOST="https://agromega.in.ua",
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
)
class CategoryMarketWidgetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root, slug="widget-potato")
        self.knowledge = CategoryFactory(parent=self.crop)
        self.market = CategoryFactory(parent=self.root, slug="widget-potato-market", value="Сорти картоплі")
        self.hub = CategoryHub.objects.create(category=self.crop, is_active=True, market_category=self.market)
        CategoryHubSection.objects.create(hub=self.hub, role="varieties", category=self.knowledge)
        self.company = Company.objects.create(
            name="Seller", website="https://seller.example", location=LocationFactory()
        )
        self.post = self.post_in(self.market, "Ажур")
        self.offer = self.offer_for(self.post, "Картопля Ажур")

    def tearDown(self):
        cache.clear()

    def post_in(self, category, title):
        post = PostFactory(rubric=category, title=title)
        post.get_absolute_url()
        return post

    def offer_for(self, post, name, **kwargs):
        return Product.objects.create(
            company=self.company, category=post.rubric, post=post, name=name, price=40, **kwargs
        )

    def context(self):
        return build_crop_hub_context(Category.objects.select_related("meta").get(pk=self.crop.pk))

    def test_widget_mirrors_category_market_without_changing_legacy_selection(self):
        # Legacy review rows, non-canonical titles and separate package records
        # retain the same behavior in both the ordinary market and this widget.
        self.offer_for(self.post, "Насіннєва картопля Ажур 1 кг")
        self.offer_for(self.post, "Unrelated historical linked product")
        before = list(market_offers().order_by("pk").values())
        result = self.context()
        widget = result["market_widget"]
        page = self.client.get(reverse("market:category", args=[self.market.slug]))
        market_posts = page.context["varieties"]
        self.assertEqual([m["value"] for m in widget["stats"]], [3, 1, 1])
        self.assertEqual(widget["items"][0]["offer_count"], market_posts[0].market_offer_count)
        self.assertEqual(widget["items"][0]["seller_count"], market_posts[0].market_seller_count)
        self.assertEqual(list(market_offers().order_by("pk").values()), before)
        self.assertFalse(result["price_summary"]["available"])

    def test_ordinary_links_render_once_and_knowledge_catalog_stays_independent(self):
        knowledge_post = self.post_in(self.knowledge, "Knowledge cultivar")
        original = Post.objects.values().get(pk=knowledge_post.pk)
        response = self.client.get(self.crop.get_absolute_url())
        widget = response.context["market_widget"]
        self.assertEqual(widget["category_id"], self.market.pk)
        self.assertEqual(response.context["knowledge_stats"][0]["value"], 1)
        self.assertEqual(response.context["featured_varieties"][0]["id"], knowledge_post.pk)
        self.assertEqual(widget["url"], reverse("market:category", args=[self.market.slug]))
        self.assertNotIn("hub=", widget["items"][0]["url"])
        self.assertContains(response, 'id="crop-market-title"', count=1)
        self.assertContains(response, "Усі пропозиції категорії")
        self.assertContains(response, widget["items"][0]["url"])
        self.assertNotContains(response, "Продавці з перевіреними пропозиціями")
        self.assertEqual(self.client.get(widget["items"][0]["url"]).status_code, 200)
        self.assertEqual(Post.objects.values().get(pk=knowledge_post.pk), original)

    def test_exact_category_not_descendants_and_no_inferred_crop_scope(self):
        child = CategoryFactory(parent=self.market)
        other = self.post_in(child, "Child cultivar")
        self.offer_for(other, "Child cultivar")
        knowledge = self.post_in(self.knowledge, "Knowledge cultivar")
        self.offer_for(knowledge, "Knowledge cultivar")
        widget = self.context()["market_widget"]
        self.assertEqual([item["id"] for item in widget["items"]], [self.post.pk])
        self.assertEqual(widget["stats"][0]["value"], 1)

    def test_switching_source_and_clearing_it_replace_cached_context(self):
        self.context()
        other_category = CategoryFactory(parent=self.root)
        other_post = self.post_in(other_category, "Other cultivar")
        self.offer_for(other_post, "Other cultivar")
        self.hub.market_category = other_category
        self.hub.save()
        widget = self.context()["market_widget"]
        self.assertEqual([item["id"] for item in widget["items"]], [other_post.pk])
        self.hub.market_category = None
        self.hub.save()
        context = self.context()
        self.assertIsNone(context["market_widget"])
        self.assertFalse(context["market_widget_configured"])
        self.assertIn("hub=widget-potato", context["marketplace_links"]["offers"])

    @override_settings(CROP_HUB_CACHE_TTL=0)
    def test_inactive_source_or_ancestor_hides_widget_without_fallback(self):
        external_root = CategoryFactory()
        external = CategoryFactory(parent=external_root)
        self.hub.market_category = external
        self.hub.save()
        self.crop.refresh_from_db()
        for category in (external, external_root):
            Category.objects.filter(pk=category.pk).update(is_active=False)
            response = self.client.get(self.crop.get_absolute_url())
            self.assertEqual(response.status_code, 200)
            self.assertIsNone(response.context["market_widget"])
            self.assertTrue(response.context["market_widget_configured"])
            self.assertNotContains(response, 'id="crop-market-title"')
            self.assertNotContains(response, "Переглянути пропозиції")
            Category.objects.filter(pk=category.pk).update(is_active=True)

    def test_preview_is_bounded_with_stable_query_count(self):
        with CaptureQueriesContext(connection) as queries:
            self.context()
        before = len(queries)
        for i in range(10):
            post = self.post_in(self.market, f"Cultivar {i}")
            self.offer_for(post, post.title)
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            context = self.context()
        self.assertEqual(len(queries), before)
        self.assertEqual(len(context["market_widget"]["items"]), 6)
        self.assertEqual(context["market_widget"]["stats"][2]["value"], 11)

    @override_settings(CROP_HUB_FRESH_DAYS=1, PRODUCT_PRICE_FRESH_DAYS=30, CROP_HUB_CACHE_TTL=0)
    def test_widget_uses_market_price_window_and_empty_state(self):
        Product.objects.filter(pk=self.offer.pk).update(price_updated_at=timezone.now() - timedelta(days=8))
        self.assertEqual(self.context()["market_widget"]["stats"][0]["value"], 1)
        Product.objects.filter(pk=self.offer.pk).update(price_updated_at=timezone.now() - timedelta(days=31))
        response = self.client.get(self.crop.get_absolute_url())
        self.assertEqual(response.context["market_widget"]["items"], [])
        self.assertContains(response, "У цій категорії поки немає пропозицій")

    def test_deleting_source_preserves_hub_and_knowledge_references(self):
        self.market.delete()
        self.hub.refresh_from_db()
        self.assertIsNone(self.hub.market_category_id)
        self.assertEqual(self.hub.sections.get().category_id, self.knowledge.pk)
        self.assertIsNone(hub_config(self.crop.slug)["market_category_id"])
