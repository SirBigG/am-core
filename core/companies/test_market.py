from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from core.classifier.models import Category
from core.posts.models import Post
from core.utils.tests.factories import CategoryFactory, LocationFactory, PostFactory

from .market import market_offers
from .models import Company, MarketPage, Product


@override_settings(HOST="https://agromega.in.ua", PRODUCT_PRICE_FRESH_DAYS=30)
class MarketTests(TestCase):
    def setUp(self):
        self.category = CategoryFactory(
            value="Сорти яблунь", slug="apple-varieties", is_active=True, parent=CategoryFactory()
        )
        self.post = PostFactory(rubric=self.category, title="Гала", status=True)
        self.company = Company.objects.create(
            name="Shop", website="https://example.com", location=LocationFactory(), active=True
        )
        self.offer = Product.objects.create(
            name="Саджанець Гала",
            company=self.company,
            category=self.category,
            post=self.post,
            price=100,
            currency="UAH",
            link="https://example.com/gala",
        )

    def test_list_category_detail_and_separate_currency_aggregation(self):
        Product.objects.create(
            name="Гала контейнер",
            company=self.company,
            category=self.category,
            post=self.post,
            price=200,
            currency="UAH",
        )
        Product.objects.create(
            name="Гала USD", company=self.company, category=self.category, post=self.post, price=10, currency="USD"
        )
        response = self.client.get(reverse("market:list"))
        self.assertEqual(response.status_code, 200)
        variety = response.context["varieties"][0]
        self.assertEqual(variety.market_offer_count, 3)
        self.assertEqual(variety.market_seller_count, 1)
        self.assertEqual(
            [(p["min"], p["max"]) for p in variety.market_prices],
            [(Decimal(100), Decimal(200)), (Decimal(10), Decimal(10))],
        )
        self.assertContains(response, f'value="{self.category.slug}"')
        self.assertEqual(self.client.get(reverse("market:category", args=[self.category.slug])).status_code, 200)
        detail = self.client.get(reverse("market:variety", args=[self.post.pk]))
        self.assertContains(detail, "https://example.com/gala")
        self.assertContains(detail, self.post.get_absolute_url())

    def test_ineligible_offers_are_excluded_everywhere(self):
        original = {
            "active": True,
            "price": 100,
            "price_updated_at": timezone.now(),
            "post_id": self.post.pk,
            "category_id": self.category.pk,
        }
        other = CategoryFactory()
        for changes in (
            {"active": False},
            {"price_updated_at": timezone.now() - timedelta(days=31)},
            {"price": 0},
            {"post_id": None},
            {"category_id": other.pk},
        ):
            with self.subTest(changes=changes):
                Product.objects.filter(pk=self.offer.pk).update(**(original | changes))
                self.assertFalse(market_offers().exists())
                response = self.client.get(reverse("market:list"))
                self.assertEqual(response.context["paginator"].count, 0)
                self.assertContains(response, "noindex,follow")
                self.assertEqual(self.client.get(reverse("market:variety", args=[self.post.pk])).status_code, 404)
        Product.objects.filter(pk=self.offer.pk).update(**original)
        for model, pk, field in (
            (Company, self.company.pk, "active"),
            (Post, self.post.pk, "status"),
            (Category, self.category.pk, "is_active"),
        ):
            model.objects.filter(pk=pk).update(**{field: False})
            self.assertFalse(market_offers().exists())
            model.objects.filter(pk=pk).update(**{field: True})

    def test_seo_configuration_canonical_and_empty_category(self):
        MarketPage.objects.create(
            category=self.category,
            label="Яблуні",
            title="Купити саджанці яблуні",
            heading="Саджанці яблуні",
            description="Порівняння цін",
            text="Текст для покупців",
        )
        url = reverse("market:category", args=[self.category.slug])
        response = self.client.get(url)
        for text in (
            "Купити саджанці яблуні",
            "Саджанці яблуні",
            "Порівняння цін",
            "Текст для покупців",
            "https://agromega.in.ua" + url,
        ):
            self.assertContains(response, text)
        self.assertContains(self.client.get(url + "?page=1"), "noindex,follow")
        self.assertEqual(self.client.get(reverse("market:category", args=["missing"])).status_code, 404)
        empty = CategoryFactory(is_active=True)
        self.assertContains(self.client.get(reverse("market:category", args=[empty.slug])), "noindex,follow")

    def test_sitemap_only_contains_available_varieties(self):
        response = self.client.get(reverse("market:sitemap"))
        self.assertContains(response, reverse("market:variety", args=[self.post.pk]))
        Product.objects.filter(pk=self.offer.pk).update(active=False)
        self.assertNotContains(
            self.client.get(reverse("market:sitemap")), reverse("market:variety", args=[self.post.pk])
        )

    def test_legacy_company_routes_and_filters(self):
        response = self.client.get(
            reverse("companies:list"), {"category": self.category.slug, "region": self.company.location.region.slug}
        )
        self.assertContains(response, self.company.name)
        self.assertContains(response, reverse("market:list"))
        self.assertEqual(self.client.get(self.company.get_absolute_url()).status_code, 200)
        self.assertNotContains(self.client.get(reverse("companies:list"), {"category": "missing"}), self.company.name)

    def test_price_range_offer(self):
        Product.objects.filter(pk=self.offer.pk).update(price=None, min_price=100, max_price=250)
        response = self.client.get(reverse("market:list"))
        self.assertEqual(response.context["varieties"][0].market_prices[0]["max"], Decimal(250))

    def test_market_pagination_and_root_seo(self):
        from unittest.mock import patch

        from .market_views import MarketListView

        other = PostFactory(rubric=self.category, title="Флоріна", status=True)
        Product.objects.create(name="Флоріна", company=self.company, category=self.category, post=other, price=120)
        MarketPage.objects.create(heading="Каталог пропозицій", title="Агромаркет AgroMega")
        with patch.object(MarketListView, "paginate_by", 1):
            response = self.client.get(reverse("market:list"))
            self.assertContains(response, "Каталог пропозицій")
            self.assertContains(response, "?page=2")
            second = self.client.get(reverse("market:list"), {"page": 2})
            self.assertEqual(second.status_code, 200)
            self.assertContains(second, "noindex,follow")
            self.assertEqual(second.context["varieties"][0].pk, other.pk)

    def test_region_filters_prices_counts_and_detail_offers(self):
        other_company = Company.objects.create(
            name="Other region shop", website="https://example.org", location=LocationFactory(), active=True
        )
        other = Product.objects.create(
            name="Other region offer", company=other_company, category=self.category, post=self.post, price=250
        )
        region = str(self.company.location.region_id)
        response = self.client.get(reverse("market:list"), {"region": region})
        variety = response.context["varieties"][0]
        self.assertEqual(variety.market_offer_count, 1)
        self.assertEqual(variety.market_prices[0]["max"], Decimal(100))
        self.assertContains(response, "noindex,follow")
        self.assertContains(response, "?region=" + region)
        self.assertNotContains(response, "site-list-card__image")
        detail = self.client.get(reverse("market:variety", args=[self.post.pk]), {"region": region})
        self.assertContains(detail, self.offer.name)
        self.assertNotContains(detail, other.name)
        self.assertEqual(self.client.get(reverse("market:list"), {"region": "missing-region"}).status_code, 404)

    def test_category_select_redirect_preserves_region_and_resets_page(self):
        region = str(self.company.location.region_id)
        response = self.client.get(
            reverse("market:list"), {"category": self.category.slug, "region": region, "page": 3}
        )
        self.assertRedirects(response, reverse("market:category", args=[self.category.slug]) + "?region=" + region)
        cleared = self.client.get(reverse("market:list"), {"category": "", "region": ""})
        self.assertRedirects(cleared, reverse("market:list"))
