from datetime import timedelta
from unittest.mock import patch

from django.contrib.sites.models import Site
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.companies.market import crop_market_offers, publication_market_context
from core.companies.models import Company, Product
from core.posts.crop_hub import build_crop_hub_context, crop_scope_for_post, hub_config
from core.posts.models import GuideSection, GuideSectionArticle, Post
from core.utils.tests.factories import CategoryFactory, LocationFactory, PostFactory


def public_post(**kwargs):
    post = PostFactory(**kwargs)
    post.get_absolute_url()
    return post


@override_settings(
    HOST="https://agromega.in.ua", CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
class CropHubTests(TestCase):
    def setUp(self):
        cache.clear()
        self.root = CategoryFactory()
        self.crop = CategoryFactory(parent=self.root, slug="kartoplya", value="Картопля")
        self.varieties = CategoryFactory(parent=self.crop, slug="kartoplia-sorty")
        self.diseases = CategoryFactory(parent=self.crop, slug="hvoroby-kartopli")
        self.hub = CategoryHub.objects.create(category=self.crop, is_active=True)
        self.variety_section = CategoryHubSection.objects.create(
            hub=self.hub, category=self.varieties, role="varieties", sort_order=10
        )
        self.disease_section = CategoryHubSection.objects.create(
            hub=self.hub, category=self.diseases, role="diseases", sort_order=20
        )
        self.post = public_post(rubric=self.varieties, title="Беллароза")
        self.company = Company.objects.create(
            name="Seller", website="https://seller.example", location=LocationFactory()
        )
        self.offer = self.make_offer()

    def tearDown(self):
        cache.clear()

    def make_offer(self, **kwargs):
        return Product.objects.create(
            **{
                "company": self.company,
                "post": self.post,
                "category": self.varieties,
                "name": self.post.title,
                "price": 100,
                "match_status": Product.MatchStatus.AUTO,
                **kwargs,
            }
        )

    def context(self):
        return build_crop_hub_context(Category.objects.select_related("meta").get(pk=self.crop.pk))

    def test_distinct_descendant_counts_visibility_and_absent_sections(self):
        deep = CategoryFactory(parent=self.varieties)
        public_post(rubric=deep)
        public_post(rubric=self.varieties, status=False)
        public_post(rubric=self.varieties, publish_date=timezone.now() + timedelta(days=1))
        hidden = CategoryFactory(parent=self.varieties, is_active=False)
        public_post(rubric=CategoryFactory(parent=hidden))
        result = self.context()
        self.assertEqual([(m["label"], m["value"]) for m in result["knowledge_stats"]], [("Сорти", 2), ("Хвороби", 0)])
        self.assertEqual(len(result["knowledge_sections"]), 2)
        self.assertNotIn("category", result["primary_actions"][0])

    def test_ordered_guides_reuse_canonical_urls_and_no_duplicate_articles(self):
        guide = public_post(rubric=self.crop)
        first = GuideSection.objects.create(category=self.crop, title="Підготовка", sort_order=1)
        second = GuideSection.objects.create(category=self.crop, title="Зберігання", sort_order=2)
        for section in (second, first):
            GuideSectionArticle.objects.create(section=section, post=guide)
        result = self.context()
        self.assertEqual([s["title"] for s in result["growing_guides"]], ["Підготовка"])
        self.assertEqual(result["growing_guides"][0]["articles"][0]["url"], guide.absolute_url)
        self.assertNotIn(guide.pk, [p["id"] for p in result["additional_articles"]])

    def test_market_dedup_distinct_sellers_and_newest_observation(self):
        self.make_offer(price=300)
        other = Company.objects.create(name="Other", website="https://other.example", location=LocationFactory())
        self.make_offer(company=other)
        result = self.context()
        self.assertEqual([m["value"] for m in result["market_stats"]], [2, 2, 1])
        rows = list(crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)))
        self.assertEqual(len(rows), 2)
        self.assertEqual(next(row.price for row in rows if row.company_id == self.company.pk), 300)
        group = result["price_overview"][0]
        self.assertEqual(group["offer_count"], 2)
        self.assertEqual((group["min"], group["max"]), (100, 300))
        response = self.client.get("/kartoplya/")
        self.assertContains(response, "Діапазон заявлених цін")
        self.assertNotContains(response, "Недостатньо порівнюваних пропозицій")

    def test_untrusted_broad_and_wrong_category_associations_excluded(self):
        originals = {"match_status": "auto", "name": self.post.title, "category_id": self.varieties.pk}
        for fields in (
            {"match_status": "review"},
            {"name": "Гербіцид Беллароза", "match_status": "confirmed"},
            {"name": "Добриво Беллароза", "match_status": "auto"},
            {"category_id": self.diseases.pk},
            {"name": "Насіннєва картопля Беллароза 1 кг", "match_status": "confirmed"},
        ):
            with self.subTest(fields=fields):
                Product.objects.filter(pk=self.offer.pk).update(**(originals | fields))
                self.assertFalse(
                    crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)).exists()
                )

    def test_invalid_prices_stale_future_and_inactive_offers_excluded(self):
        now = timezone.now()
        originals = {"price": 100, "price_updated_at": now, "active": True}
        for fields in (
            {"price": None},
            {"price": 0},
            {"price": -5},
            {"price_updated_at": now - timedelta(days=31)},
            {"price_updated_at": now + timedelta(days=1)},
            {"active": False},
        ):
            with self.subTest(fields=fields):
                Product.objects.filter(pk=self.offer.pk).update(**(originals | fields))
                self.assertFalse(
                    crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)).exists()
                )
        Product.objects.filter(pk=self.offer.pk).update(**originals)
        for model, pk, field in (
            (Post, self.post.pk, "status"),
            (Company, self.company.pk, "active"),
            (Category, self.root.pk, "is_active"),
        ):
            model.objects.filter(pk=pk).update(**{field: False})
            self.assertFalse(
                crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)).exists()
            )
            model.objects.filter(pk=pk).update(**{field: True})

    def test_no_price_summary_without_verified_units_even_above_threshold(self):
        for index in range(6):
            company = Company.objects.create(
                name=f"Seller {index}", website="https://seller.example", location=LocationFactory()
            )
            post = public_post(rubric=self.varieties, title=f"Cultivar {index}")
            self.make_offer(company=company, post=post, name=post.title)
        self.assertGreater(self.context()["market_stats"][0]["value"], 5)
        self.assertFalse(self.context()["price_summary"]["available"])
        self.assertIsNone(self.context()["price_summary"]["unit"])
        # Package text, prices and currencies cannot manufacture measured units.
        for name in ("Беллароза 1 кг", "Беллароза 25 кг", "Беллароза 10 шт", "Беллароза упаковка"):
            self.make_offer(name=name, match_status="confirmed", currency="USD")
        cache.clear()
        self.assertEqual(self.context()["market_stats"][0]["value"], 7)
        self.assertFalse(self.context()["price_summary"]["available"])

    def test_market_links_filters_sellers_variety_and_scope_preservation(self):
        self.make_offer(name="Гербіцид Беллароза", match_status="confirmed")
        result = self.context()
        response = self.client.get(result["marketplace_links"]["offers"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 1)
        self.assertEqual(response.context["varieties"][0].market_offer_count, 1)
        self.assertContains(response, 'name="hub" value="kartoplya"')
        self.assertContains(response, "?hub=kartoplya")
        detail = reverse("market:variety", args=[self.post.pk]) + "?hub=kartoplya"
        self.assertEqual(self.client.get(detail).context["variety"].market_offer_count, 1)
        companies = self.client.get(result["marketplace_links"]["sellers"])
        self.assertEqual(list(companies.context["companies"]), [self.company])
        self.assertContains(companies, 'name="hub" value="kartoplya"')
        for url in (reverse("market:list"), reverse("companies:list"), reverse("market:variety", args=[self.post.pk])):
            self.assertEqual(self.client.get(url, {"hub": "missing"}).status_code, 404)
        redirect = self.client.get(reverse("market:list"), {"category": self.varieties.slug, "hub": self.crop.slug})
        self.assertIn("hub=kartoplya", redirect.url)
        self.assertEqual(self.client.get(redirect.url).status_code, 200)

    def test_empty_render_seo_and_all_card_destinations(self):
        Product.objects.all().delete()
        response = self.client.get("/kartoplya/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "поки немає актуальних пропозицій із цінами")
        self.assertContains(response, "<h1 ", count=1)
        self.assertContains(response, "BreadcrumbList")
        self.assertContains(response, 'rel="canonical"')
        for item in response.context["knowledge_sections"] + response.context["market_stats"]:
            self.assertEqual(self.client.get(item["url"]).status_code, 200)
        self.assertEqual(self.client.get(self.post.absolute_url).status_code, 200)
        self.hub.sections.all().delete()
        self.assertEqual(self.client.get("/kartoplya/").status_code, 200)

    def test_reuse_second_crop_and_do_not_count_other_tree(self):
        apple = CategoryFactory(parent=self.root, slug="apples", value="Яблуні")
        varieties = CategoryFactory(parent=apple, slug="apple-varieties")
        public_post(rubric=varieties)
        apple_hub = CategoryHub.objects.create(category=apple, is_active=True)
        CategoryHubSection.objects.create(hub=apple_hub, category=varieties, role="varieties")
        self.assertEqual(self.client.get("/apples/").context["knowledge_stats"][0]["value"], 1)
        self.assertEqual(self.context()["knowledge_stats"][0]["value"], 1)

    def test_site_locale_allowlists_and_cache_namespaces(self):
        site = Site.objects.create(domain="hub.example", name="Hub")
        self.hub.site = site
        self.hub.locale = "uk"
        self.hub.save()
        self.assertIsNotNone(hub_config("kartoplya", site=site.pk, locale="uk"))
        self.assertIsNone(hub_config("kartoplya", site=site.pk + 100, locale="uk"))
        self.assertIsNone(hub_config("kartoplya", site=site.pk, locale="es"))
        self.hub.site = None
        self.hub.locale = ""
        self.hub.save()
        self.context()
        with patch("core.posts.crop_hub._build_context", side_effect=AssertionError("cache miss")):
            self.context()
            with self.assertRaises(AssertionError):
                build_crop_hub_context(self.crop, site="other")
            with self.assertRaises(AssertionError):
                build_crop_hub_context(self.crop, locale="es")

    def test_cache_expiry_and_bounded_query_cost(self):
        crop = Category.objects.select_related("meta").get(pk=self.crop.pk)
        with CaptureQueriesContext(connection) as queries:
            build_crop_hub_context(crop)
        cold_count = len(queries)
        with self.assertNumQueries(2):
            build_crop_hub_context(crop)
        for index in range(10):
            self.make_offer()
        cache.clear()
        with CaptureQueriesContext(connection) as queries:
            build_crop_hub_context(crop)
        self.assertEqual(len(queries), cold_count)
        self.assertLess(cold_count, 16)
        with override_settings(CROP_HUB_CACHE_TTL=0):
            cache.clear()
            self.context()
            Product.objects.all().delete()
            self.assertEqual(self.context()["market_stats"][0]["value"], 0)

    def test_inactive_hub_404_even_with_cached_context(self):
        self.context()
        Category.objects.filter(pk=self.root.pk).update(is_active=False)
        self.assertEqual(self.client.get("/kartoplya/").status_code, 404)

    def test_hub_alias_redirects_to_saved_canonical_and_wrong_parent_is_404(self):
        response = self.client.get(f"/{self.root.slug}/kartoplya/")
        self.assertRedirects(response, "/kartoplya/", status_code=301)
        self.assertEqual(self.client.get("/wrong-parent/kartoplya/").status_code, 404)
        response = self.client.get("/kartoplya/?utm_source=test")
        self.assertContains(response, 'rel="canonical" href="https://agromega.in.ua/kartoplya/"')

    def test_strict_filters_remain_applied_with_region_and_category(self):
        response = self.client.get(
            reverse("market:list"),
            {
                "hub": "kartoplya",
                "region": self.company.location.region_id,
            },
        )
        self.assertEqual(response.context["varieties"][0].market_offer_count, 1)
        self.assertContains(response, "hub=kartoplya")
        self.assertEqual(
            self.client.get(
                reverse("companies:list"),
                {
                    "hub": "kartoplya",
                    "category": self.diseases.slug,
                },
            )
            .context["paginator"]
            .count,
            0,
        )
        response = self.client.get(reverse("market:variety", args=[self.post.pk]), {"hub": "kartoplya"})
        self.assertContains(response, f"/agromarket/category/{self.varieties.slug}/?hub=kartoplya")

    @override_settings(CROP_HUB_FRESH_DAYS=7)
    def test_freshness_window_is_configurable(self):
        Product.objects.filter(pk=self.offer.pk).update(price_updated_at=timezone.now() - timedelta(days=8))
        self.assertFalse(crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)).exists())

    def test_catalog_article_uses_strict_market_scope(self):
        context = publication_market_context(self.post, crop_scope=crop_scope_for_post(self.post))
        self.assertTrue(context["can_show"])
        self.assertTrue(context["market_url"].endswith("?hub=kartoplya"))
        self.assertContains(self.client.get(self.post.absolute_url), context["market_url"])
        Product.objects.filter(pk=self.offer.pk).update(name="Гербіцид Беллароза", match_status="confirmed")
        self.assertFalse(publication_market_context(self.post, crop_scope=crop_scope_for_post(self.post))["can_show"])

    def test_configuration_edits_replace_cached_context_and_disable_scope(self):
        self.context()
        self.variety_section.title = "Updated varieties"
        self.variety_section.save()
        self.assertEqual(self.context()["knowledge_sections"][0]["label"], "Updated varieties")
        self.variety_section.is_active = False
        self.variety_section.save()
        self.assertEqual(self.context()["market_stats"][0]["value"], 0)
        self.hub.is_active = False
        self.hub.save()
        self.assertIsNone(self.context())
        self.assertEqual(self.client.get("/agromarket/?hub=kartoplya").status_code, 404)
        self.assertTemplateUsed(self.client.get("/kartoplya/"), "posts/parent_index.html")

    def test_extra_sections_order_labels_and_guide_source_are_dynamic(self):
        guide_category = CategoryFactory(parent=self.crop)
        guide = public_post(rubric=guide_category)
        step = GuideSection.objects.create(category=guide_category, title="Planting")
        GuideSectionArticle.objects.create(section=step, post=guide)
        extra = CategoryHubSection.objects.create(
            hub=self.hub,
            category=guide_category,
            role="additional",
            title="Soil",
            sort_order=0,
        )
        self.hub.guide_category = guide_category
        self.hub.save()
        result = self.context()
        self.assertEqual(result["knowledge_sections"][0]["label"], "Soil")
        self.assertEqual(result["growing_guides"][0]["articles"][0]["id"], guide.pk)
        # Category renames remain FK-backed; no config string needs updating.
        Category.objects.filter(pk=extra.category_id).update(slug="renamed-guide")
        self.assertEqual(hub_config(self.crop.slug)["sections"][0]["category_id"], extra.category_id)

    def test_external_catalog_and_guide_references_preserve_public_market_scope(self):
        external = CategoryFactory(parent=self.root)
        post = public_post(rubric=external, title="External cultivar")
        self.make_offer(post=post, category=external, name=post.title)
        self.variety_section.category = external
        self.variety_section.full_clean()
        self.variety_section.save()
        step = GuideSection.objects.create(category=external, title="External guide")
        GuideSectionArticle.objects.create(section=step, post=post)
        self.hub.guide_category = external
        self.hub.full_clean()
        self.hub.save()
        result = self.context()
        self.assertEqual(result["knowledge_stats"][0]["value"], 1)
        self.assertEqual(result["market_stats"][0]["value"], 1)
        self.assertEqual(result["growing_guides"][0]["title"], "External guide")
        scope = crop_scope_for_post(post)
        self.assertEqual(scope[0].pk, self.crop.pk)
        self.assertTrue(publication_market_context(post, crop_scope=scope)["market_url"].endswith("?hub=kartoplya"))
        Category.objects.filter(pk=external.pk).update(is_active=False)
        self.assertFalse(crop_market_offers(Category.objects.get(pk=self.crop.pk), hub_config(self.crop.slug)).exists())

    def test_crop_landing_composes_legacy_sibling_catalog_and_guide(self):
        legacy = CategoryFactory(parent=self.root, slug="koreneplidni")
        catalog = CategoryFactory(parent=legacy, slug="sorty-kartopli")
        guide_category = CategoryFactory(parent=legacy, slug="potato-guide", presentation_mode="guide_hub")
        cultivar = public_post(rubric=catalog, title="Legacy cultivar")
        guide_post = public_post(rubric=guide_category, title="Legacy growing article")
        unrelated = public_post(rubric=CategoryFactory(parent=legacy), title="Carrot cultivar")
        original_urls = dict(Post.objects.values_list("pk", "absolute_url"))
        step = GuideSection.objects.create(category=guide_category, title="Вибір і догляд")
        GuideSectionArticle.objects.create(section=step, post=guide_post)
        self.variety_section.category = catalog
        self.variety_section.save()
        self.disease_section.delete()
        self.hub.guide_category = guide_category
        self.hub.save()
        self.make_offer(post=cultivar, category=catalog, name=cultivar.title)
        self.make_offer(post=unrelated, category=unrelated.rubric, name=unrelated.title)
        catalog.refresh_from_db()
        guide_category.refresh_from_db()

        response = self.client.get("/kartoplya/")
        self.assertTemplateUsed(response, "posts/crop_hub.html")
        self.assertEqual(Category.objects.get(pk=self.crop.pk).level, Category.objects.get(pk=legacy.pk).level)
        self.assertEqual([item["value"] for item in response.context["knowledge_stats"]], [1, 1])
        self.assertContains(response, catalog.absolute_url)
        self.assertContains(response, guide_post.absolute_url)
        self.assertNotContains(response, unrelated.title)
        self.assertEqual([item["value"] for item in response.context["market_stats"]], [1, 1, 1])
        market = self.client.get(response.context["marketplace_links"]["offers"])
        self.assertEqual([item.pk for item in market.context["varieties"]], [cultivar.pk])
        sellers = self.client.get(response.context["marketplace_links"]["sellers"])
        self.assertEqual(list(sellers.context["companies"]), [self.company])
        self.assertTemplateUsed(self.client.get(guide_category.absolute_url), "posts/guide_hub.html")
        self.assertEqual(dict(Post.objects.values_list("pk", "absolute_url")), original_urls)
        self.assertEqual(self.client.get(cultivar.absolute_url).status_code, 200)

    def test_market_navigation_and_selectors_keep_crop_identity(self):
        other_catalog = CategoryFactory(parent=self.root, value="Carrots")
        other_post = public_post(rubric=other_catalog, title="Other cultivar")
        self.make_offer(post=other_post, category=other_catalog, name=other_post.title)
        market = self.client.get("/agromarket/?hub=kartoplya")
        self.assertEqual([item.pk for item in market.context["categories"]], [self.varieties.pk])
        companies = self.client.get("/companies/?hub=kartoplya")
        self.assertEqual(
            list(companies.context["company_categories"].values_list("pk", flat=True)), [self.varieties.pk]
        )
        for response, destination in ((market, "/agromarket/"), (companies, "/companies/")):
            self.assertEqual(response.context["crop_hub_category"].pk, self.crop.pk)
            self.assertContains(
                response,
                f'<a href="{destination}?hub=kartoplya" class="align-self-end">Скинути</a>',
                html=True,
            )
            self.assertContains(response, 'href="/kartoplya/"')
        Product.objects.filter(pk=self.offer.pk).delete()
        empty = self.client.get("/agromarket/?hub=kartoplya")
        self.assertContains(empty, 'href="/companies/?hub=kartoplya">Переглянути компанії')
