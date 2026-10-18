from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.adverts.models import Advert
from core.classifier.models import Category
from core.companies.models import Company, Product
from core.diary.models import Diary
from core.posts.models import Post, SearchStatistic
from core.registry.models import Variety, VarietyCategory
from core.search.indexing import sync_index
from core.search.models import ResourceType, SearchDirtyScope, SearchDocument, SearchIndexState
from core.search.query import result_counts, search_documents
from core.search.sources import hydrate_market, local_url, normalize, post_url
from core.search.views import UnifiedSearchView
from core.utils.tests.factories import CategoryFactory, EventFactory, LocationFactory, PostFactory, UserFactory


@override_settings(UNIFIED_SEARCH_ENABLED=True, PRODUCT_PRICE_FRESH_DAYS=30, ADVERT_ACTIVE_DAYS=30)
class SearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.now = timezone.now()
        cls.root = CategoryFactory()
        cls.parent = CategoryFactory(parent=cls.root)
        cls.category = CategoryFactory(parent=cls.parent, value="Соната категорія")
        cls.user = UserFactory()
        cls.location = LocationFactory()
        cls.post = PostFactory(title="Соната", rubric=cls.category, publisher=cls.user)
        Post.objects.filter(pk=cls.post.pk).update(absolute_url=post_url(cls.post))
        cls.company = Company.objects.create(
            name="Соната магазин",
            website="https://example.com",
            location=cls.location,
            description="Магазин саджанців",
            parser_map={"private": "секретний-маркер"},
        )
        cls.offer = Product.objects.create(
            name="Соната контейнерна",
            post=cls.post,
            category=cls.category,
            company=cls.company,
            price=100,
            currency="UAH",
        )
        cls.advert = Advert.objects.create(
            title="Соната оголошення",
            description="Продаємо саджанці",
            category=cls.category,
            contact="секретний-маркер",
            updated=cls.now,
        )
        cls.event = EventFactory(title="Соната виставка", user=cls.user, location=cls.location)
        cls.diary = Diary.objects.create(title="Соната щоденник", description="Мій сад", public=True, user=cls.user)
        cls.registry = VarietyCategory.objects.create(title="Соната реєстр", slug="sonata-registry")
        cls.registry_child = VarietyCategory.objects.create(
            title="Соната сорти", slug="sonata-varieties", parent=cls.registry
        )
        Variety.objects.create(title="Соната", title_original="UniqueRegistryAlias", publication=cls.post)
        sync_index(rebuild=True)

    def ids(self, query="Соната", **kwargs):
        return set(search_documents(query, **kwargs).values_list("resource_type", "source_id"))

    def test_all_owned_resource_types_have_positive_matches(self):
        self.assertEqual({kind for kind, _ in self.ids()}, set(ResourceType.values))

    def test_diaries_and_registry_are_not_indexed_or_offered_as_filters(self):
        self.assertFalse(SearchDocument.objects.filter(resource_type__in=["diary", "registry"]).exists())
        response = self.client.get("/search/", {"q": "Соната"})
        self.assertNotContains(response, "Щоденники")
        self.assertNotContains(response, "Реєстр сортів")
        for kind in ("diary", "registry"):
            self.assertEqual(self.client.get("/search/", {"q": "Соната", "type": kind}).status_code, 404)

    def test_removed_sources_do_not_invalidate_search(self):
        Diary.objects.filter(pk=self.diary.pk).update(title="Змінений щоденник")
        VarietyCategory.objects.filter(pk=self.registry.pk).update(title="Змінений реєстр")
        Variety.objects.filter(publication=self.post).update(title_original="Змінений сорт")
        self.assertFalse(SearchDirtyScope.objects.exists())

    def test_removed_types_are_hidden_even_in_an_old_index(self):
        generation = SearchIndexState.objects.get().active_generation
        template = SearchDocument.objects.filter(resource_type="post").get(source_id=self.post.pk)
        for kind in ("diary", "registry"):
            SearchDocument.objects.create(
                generation=generation,
                resource_type=kind,
                source_id=99999,
                title="Соната",
                normalized_title="соната",
                canonical_url="/removed/",
                search_vector=template.search_vector,
            )
        self.assertFalse(search_documents("Соната").filter(resource_type__in=["diary", "registry"]).exists())

    def test_exact_title_precedes_body_only_match_and_fuzzy_match(self):
        body = PostFactory(title="Інший матеріал", text="Соната", rubric=self.category, publisher=self.user)
        fuzzy = PostFactory(title="Сонатаа", rubric=self.category, publisher=self.user)
        for post in (body, fuzzy):
            Post.objects.filter(pk=post.pk).update(absolute_url=post_url(post))
        sync_index()
        results = list(search_documents("Соната").filter(resource_type="post"))
        self.assertEqual((results[0].resource_type, results[0].source_id), ("post", self.post.pk))
        self.assertLess(
            next(i for i, d in enumerate(results) if d.source_id == self.post.pk and d.resource_type == "post"),
            next(i for i, d in enumerate(results) if d.source_id == body.pk and d.resource_type == "post"),
        )

    def test_fuzzy_title_finds_typo(self):
        self.assertIn(("post", self.post.pk), self.ids("Сонатта"))

    def test_registry_alias_is_excluded_but_tags_find_catalog_post(self):
        self.assertFalse(search_documents("UniqueRegistryAlias").exists())
        self.post.tags.add("Унікальнийтег")
        sync_index()
        self.assertIn(("post", self.post.pk), self.ids("Унікальнийтег"))

    def test_product_name_only_finds_one_market_identity(self):
        Product.objects.filter(pk=self.offer.pk).update(name="Рідкіснийконтейнер")
        Product.objects.bulk_create(
            [
                Product(
                    name="Рідкіснийконтейнер",
                    post=self.post,
                    category=self.category,
                    company=self.company,
                    price=200,
                    price_updated_at=self.now,
                ),
            ]
        )
        sync_index()
        self.assertEqual(
            list(search_documents("Рідкіснийконтейнер").values_list("resource_type", "source_id")),
            [("market", self.post.pk)],
        )

    def test_market_prices_are_current_and_currencies_remain_separate(self):
        Product.objects.create(
            name="Соната", post=self.post, category=self.category, company=self.company, price=10, currency="USD"
        )
        Product.objects.create(
            name="Соната", post=self.post, category=self.category, company=self.company, price=200, currency="UAH"
        )
        documents = hydrate_market(list(search_documents("Соната").filter(resource_type="market")))
        market = documents[0].market
        self.assertEqual(market.market_seller_count, 1)
        self.assertEqual(market.market_offer_count, 3)
        prices = {price["currency"]: (price["min"], price["max"]) for price in market.market_prices}
        self.assertEqual(prices["грн."], (Decimal(100), Decimal(200)))
        self.assertEqual(prices["$"], (Decimal(10), Decimal(10)))

    def test_market_expiry_is_immediate_without_worker(self):
        Product.objects.filter(pk=self.offer.pk).update(price_updated_at=self.now - timedelta(days=31))
        self.assertNotIn(("market", self.post.pk), self.ids())

    def test_future_prices_are_not_public(self):
        Product.objects.filter(pk=self.offer.pk).update(price_updated_at=self.now + timedelta(days=1))
        self.assertNotIn(("market", self.post.pk), self.ids())

    def test_wrong_market_identity_is_not_public(self):
        Product.objects.filter(pk=self.offer.pk).update(category=self.parent)
        self.assertNotIn(("market", self.post.pk), self.ids())

    def test_inactive_seller_immediately_hides_market_and_company(self):
        Company.objects.filter(pk=self.company.pk).update(active=False)
        ids = self.ids()
        self.assertNotIn(("market", self.post.pk), ids)
        self.assertNotIn(("company", self.company.pk), ids)

    def test_hidden_ancestor_excludes_articles_market_categories_and_adverts(self):
        Category.objects.filter(pk=self.parent.pk).update(is_active=False)
        ids = self.ids()
        for key in [
            ("post", self.post.pk),
            ("market", self.post.pk),
            ("category", self.category.pk),
            ("advert", self.advert.pk),
        ]:
            self.assertNotIn(key, ids)
        self.assertNotIn("post", result_counts(search_documents("Соната")))

    def test_unpublish_and_future_publication_are_immediate(self):
        for changes in ({"status": False}, {"status": True, "publish_date": self.now + timedelta(days=1)}):
            with self.subTest(changes=changes):
                Post.objects.filter(pk=self.post.pk).update(**changes)
                self.assertNotIn(("post", self.post.pk), self.ids())
                self.assertNotIn(("market", self.post.pk), self.ids())

    def test_expired_and_inactive_adverts_are_not_searchable(self):
        for changes in ({"updated": self.now - timedelta(days=31)}, {"is_active": False}):
            with self.subTest(changes=changes):
                Advert.objects.filter(pk=self.advert.pk).update(**changes)
                self.assertNotIn(("advert", self.advert.pk), self.ids())

    def test_ended_events_are_only_in_archive(self):
        type(self.event).objects.filter(pk=self.event.pk).update(stop=self.now - timedelta(days=1))
        self.assertNotIn(("event", self.event.pk), self.ids())
        self.assertIn(("event", self.event.pk), self.ids(archive=True))

    def test_deleted_source_disappears_before_worker_then_document_is_removed(self):
        Advert.objects.filter(pk=self.advert.pk).delete()
        self.assertNotIn(("advert", self.advert.pk), self.ids())
        sync_index()
        self.assertFalse(SearchDocument.objects.filter(resource_type="advert", source_id=self.advert.pk).exists())

    def test_bulk_update_and_bulk_create_are_durable_and_searchable_after_sync(self):
        Advert.objects.bulk_create([Advert(title="Новийунікальний", contact="test")])
        Post.objects.filter(pk=self.post.pk).update(title="Іншийунікальний")
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="advert").exists())
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="post").exists())
        sync_index()
        self.assertTrue(search_documents("Новийунікальний").exists())
        self.assertIn(("post", self.post.pk), self.ids("Іншийунікальний"))
        self.assertFalse(SearchDirtyScope.objects.exists())

    def test_raw_sql_writes_invalidate(self):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE post SET title = %s WHERE id = %s", ["RawSQLTitle", self.post.pk])
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="post").exists())
        sync_index()
        self.assertIn(("post", self.post.pk), self.ids("RawSQLTitle"))

    def test_view_counters_do_not_dirty_index(self):
        Post.objects.filter(pk=self.post.pk).update(hits=123)
        Advert.objects.filter(pk=self.advert.pk).update(views=123)
        self.assertFalse(SearchDirtyScope.objects.exists())

    def test_rebuild_is_idempotent_and_replaces_generation(self):
        before = self.ids()
        generation = SearchIndexState.objects.get().active_generation
        count = SearchDocument.objects.count()
        sync_index(rebuild=True)
        self.assertNotEqual(SearchIndexState.objects.get().active_generation, generation)
        self.assertEqual(self.ids(), before)
        self.assertEqual(SearchDocument.objects.count(), count)
        self.assertEqual(sync_index(), 0)

    def test_failed_rebuild_keeps_active_generation_documents_and_queue(self):
        Advert.objects.filter(pk=self.advert.pk).update(title="Новийзаголовок")
        generation = SearchIndexState.objects.get().active_generation
        count = SearchDocument.objects.count()
        with patch("core.search.indexing.write_scope", side_effect=RuntimeError("test failure")):
            with self.assertRaises(RuntimeError):
                sync_index(rebuild=True)
        self.assertEqual(SearchIndexState.objects.get().active_generation, generation)
        self.assertEqual(SearchDocument.objects.count(), count)
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="advert").exists())
        sync_index()
        self.assertIn(("advert", self.advert.pk), self.ids("Новийзаголовок"))

    def test_change_during_build_survives_compare_and_delete(self):
        from core.search.indexing import write_scope

        Advert.objects.filter(pk=self.advert.pk).update(title="Першазміна")

        def concurrent_change(generation, kind):
            write_scope(generation, kind)
            if kind == "advert":
                Advert.objects.filter(pk=self.advert.pk).update(title="Другазміна")

        with patch("core.search.indexing.write_scope", side_effect=concurrent_change):
            sync_index()
        self.assertTrue(SearchDirtyScope.objects.filter(resource_type="advert").exists())
        sync_index()
        self.assertIn(("advert", self.advert.pk), self.ids("Другазміна"))

    def test_html_is_plain_and_output_is_escaped(self):
        Advert.objects.filter(pk=self.advert.pk).update(
            title="Соната <img src=x onerror=alert(1)>",
            description="<b>Вміст</b> &lt;script&gt;alert(1)&lt;/script&gt;",
        )
        sync_index()
        response = self.client.get("/search/", {"q": "Соната", "type": "advert"})
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertNotContains(response, "<img src=x")
        self.assertContains(response, "&lt;script&gt;alert(1)&lt;/script&gt;")

    def test_private_fields_are_never_indexed(self):
        self.assertFalse(search_documents("секретний-маркер").exists())

    def test_page_has_type_counts_and_noindex(self):
        response = self.client.get("/search/", {"q": "Соната"})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "search/results.html")
        self.assertEqual(response.context["paginator"].count, len(self.ids()))
        self.assertContains(response, '<meta name="robots" content="noindex,follow">', html=True)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertContains(response, reverse("market:variety", args=[self.post.pk]))

    def test_type_filter_counts_and_encoded_pagination(self):
        Advert.objects.create(title="Соната друге оголошення", contact="test")
        sync_index()
        with patch.object(UnifiedSearchView, "paginate_by", 1):
            first = self.client.get("/search/", {"q": "Соната", "type": "advert"})
            self.assertEqual(first.context["paginator"].count, 2)
            self.assertTrue(first.context["next_url"].startswith("?q=%D0"))
            second = self.client.get("/search/" + first.context["next_url"])
        self.assertNotEqual(first.context["object_list"][0].source_id, second.context["object_list"][0].source_id)
        self.assertEqual(
            [f["count"] for f in first.context["filters"]], [f["count"] for f in second.context["filters"]]
        )
        self.assertEqual(SearchStatistic.objects.count(), 0)

    def test_query_length_whitespace_and_search_statistics(self):
        response = self.client.get("/search/", {"q": "  Соната   "})
        self.assertEqual(response.context["query"], "Соната")
        self.client.get("/search/", {"q": "Соната", "page": 1})
        self.client.get("/search/", {"q": "Соната", "type": "market"})
        self.assertEqual(SearchStatistic.objects.count(), 1)
        long = self.client.get("/search/", {"q": "x" * 1000})
        self.assertEqual(len(long.context["query"]), 255)
        self.assertLessEqual(len(SearchStatistic.objects.latest("created").search_phrase), 255)

    def test_blank_query_and_unknown_type(self):
        response = self.client.get("/search/", {"q": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["paginator"].count, 0)
        self.assertEqual(SearchStatistic.objects.count(), 0)
        self.assertEqual(self.client.get("/search/", {"q": "Соната", "type": "unknown"}).status_code, 404)

    def test_unbuilt_index_has_distinct_state(self):
        SearchIndexState.objects.all().delete()
        response = self.client.get("/search/", {"q": "Соната"})
        self.assertContains(response, "Пошук готується до роботи")
        self.assertNotContains(response, "Нічого не знайшли")

    @override_settings(UNIFIED_SEARCH_ENABLED=False)
    def test_feature_flag_restores_legacy_search(self):
        response = self.client.get("/search/", {"q": "Соната"})
        self.assertTemplateUsed(response, "posts/search.html")

    def test_normalization_and_local_urls(self):
        self.assertEqual(normalize("  М’ята–F1  "), "м'ята-f1")
        for value in ("https://evil.example", "//evil.example", "/\\evil.example", "/\nunsafe"):
            self.assertFalse(local_url(value))
        self.assertTrue(local_url("/agromarket/variety/1/"))

    def test_index_has_gin_operator_paths(self):
        # Tiny fixtures normally favor scans. Disable seqscan only to verify the
        # operators can use the installed indexes, not to claim a latency win.
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL enable_seqscan = off")
        from django.contrib.postgres.search import SearchQuery

        fts = SearchDocument.objects.filter(search_vector=SearchQuery("Соната", config="simple"))
        fuzzy = SearchDocument.objects.filter(normalized_title__trigram_similar="сонатта")
        self.assertIn("search_document_fts", fts.explain())
        self.assertIn("search_document_title_trgm", fuzzy.explain())
