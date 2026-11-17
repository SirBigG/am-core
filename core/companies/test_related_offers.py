from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from core.catalog.public_blocks import public_blocks
from core.catalog.tests.test_public_blocks import PublicBlockFixtures
from core.posts.models import Post
from core.utils.tests.factories import LocationFactory

from .models import Company, Product, RelatedOfferPublication
from .related_offers import offer_link, related_offer_counts


class RelatedOfferTests(PublicBlockFixtures, TestCase):
    def setUp(self):
        super().setUp()
        self.approved_record()
        self.activate(self.save())
        self.post = Post.objects.get(entity=self.preparation)
        self.seller = Company.objects.create(
            name="Scoped seller", location=LocationFactory(), website="https://shop.example/"
        )
        self.result = public_blocks(
            self.category, self.path, self.anonymous.get(self.path).wsgi_request.GET, category=True
        )
        self.block = self.result["blocks"][0]
        self.cards = self.block["selection"]["results"]
        self.context = self.result["market_context"]
        self.link = offer_link(
            self.context,
            anchor_type="category",
            anchor_id=self.category.pk,
            query={},
            block=self.block,
            card=self.cards[0],
        )

    def offer(self, **changes):
        fields = dict(
            post=self.post,
            category=self.post.rubric,
            company=self.seller,
            price=100,
            currency="UAH",
            name="Vendor label",
            match_status=Product.MatchStatus.CONFIRMED,
            link="https://shop.example/pack",
        )
        product = Product.objects.create(**(fields | changes))
        return product

    def allow(self, offer, **changes):
        return RelatedOfferPublication.objects.create(
            **dict(
                product=offer,
                site=self.site,
                post=self.post,
                entity=self.preparation,
                country="UA",
                content_locale="uk",
                enabled=True,
                package_label="Пляшка 100 мл",
            )
            | changes
        )

    def counts(self):
        return related_offer_counts(self.context, self.cards)

    def test_counts_and_display_preserve_packages_and_distinct_sellers(self):
        first, second = self.offer(), self.offer(currency="USD", price=5, name="Second pack")
        self.allow(first)
        self.allow(second, package_label="Каністра 5 л")
        with CaptureQueriesContext(connection) as queries:
            counts = self.counts()
        self.assertEqual(len(queries), 1)
        self.assertEqual(counts[str(self.preparation.pk)], {"offers": 2, "sellers": 1})
        page = self.anonymous.get(self.link)
        for value in ("Пляшка 100 мл", "Каністра 5 л", "USD", "UAH", "Scoped seller", "https://shop.example/pack"):
            self.assertContains(page, value)
        self.assertContains(page, "Пропозицій: 2 · Продавців: 1")
        self.assertIn("no-store", page["Cache-Control"])
        self.assertEqual(page["X-Robots-Tag"], "noindex, follow")

    def test_fail_closed_on_membership_and_match_price_and_seller(self):
        product = self.offer(name=self.post.title)
        self.assertEqual(self.counts(), {})
        membership = self.allow(product)
        baseline = {"match_status": Product.MatchStatus.CONFIRMED, "price": 100, "currency": "UAH"}
        Product.objects.filter(pk=product.pk).update(**baseline)
        self.assertTrue(self.counts())
        for changes in (
            {"active": False},
            {"post_id": None},
            {"match_status": Product.MatchStatus.REVIEW},
            {"match_status": Product.MatchStatus.AUTO},
            {"price": 0},
            {"currency": ""},
            {"price": None, "min_price": 20, "max_price": 10},
            {"price_updated_at": timezone.now() - timedelta(days=365)},
            {"price_updated_at": timezone.now() + timedelta(days=1)},
        ):
            with self.subTest(changes=changes), transaction.atomic():
                Product.objects.filter(pk=product.pk).update(**changes)
                self.assertEqual(self.counts(), {})
                transaction.set_rollback(True)
        for changes in (
            {"country": "GB"},
            {"content_locale": "en"},
            {"site_id": self.other_site.pk},
            {"enabled": False},
        ):
            with self.subTest(changes=changes), transaction.atomic():
                RelatedOfferPublication.objects.filter(pk=membership.pk).update(**changes)
                self.assertEqual(self.counts(), {})
                transaction.set_rollback(True)
        Company.objects.filter(pk=self.seller.pk).update(active=False)
        self.assertContains(self.anonymous.get(self.link), "Чинних пропозицій продавців поки немає.")
        self.assertEqual(len(self.anonymous.get(self.api_url()).json()["blocks"]), 1)

    def test_stale_context_and_import_cannot_bypass_scope(self):
        product = self.offer()
        membership = self.allow(product)
        self.assertContains(self.anonymous.get(self.link), self.seller.name)
        with override_settings(SITE_ID=self.other_site.pk, RELATED_CATALOG_MARKETS={self.other_site.pk: "UA"}):
            self.assertEqual(self.anonymous.get(self.link).status_code, 404)
        self.assertEqual(self.anonymous.get(self.link + "&selection=another").status_code, 404)
        self.assertEqual(self.anonymous.get(self.link + "corrupt").status_code, 404)
        Post.objects.filter(entity=self.target).update(status=False)
        self.assertEqual(self.anonymous.get(self.link).status_code, 404)
        product.refresh_from_db()
        self.assertEqual(product.post_id, self.post.pk)
        membership.entity = self.target
        with self.assertRaises(ValidationError):
            membership.full_clean()

    def test_seller_url_is_only_safe_http(self):
        product = self.offer(link="javascript:alert(1)")
        self.allow(product)
        response = self.anonymous.get(self.link)
        self.assertContains(response, self.seller.name)
        self.assertNotContains(response, "javascript:alert")

    def test_admin_grants_and_rejects_duplicate_scopes(self):
        from django.contrib.auth.models import Permission
        from django.test import Client

        product = self.offer()
        self.actor.user_permissions.add(
            *Permission.objects.filter(
                content_type__app_label="companies", codename__endswith="relatedofferpublication"
            )
        )
        editor = Client()
        editor.force_login(self.actor)
        add = reverse("admin:companies_relatedofferpublication_add")
        data = {
            "product": product.pk,
            "post": self.post.pk,
            "entity": self.preparation.pk,
            "country": "UA",
            "content_locale": "uk",
            "enabled": "on",
            "package_label": "100 мл",
        }
        with override_settings(SITE_ID=self.other_site.pk):
            self.assertEqual(editor.post(add, data).status_code, 403)
        added = editor.post(add, data | {"site": self.other_site.pk})
        self.assertEqual(added.status_code, 302)
        self.assertEqual(RelatedOfferPublication.objects.get().site_id, self.site.pk)
        duplicate = editor.post(add, data)
        self.assertContains(duplicate, "вже є дозвіл")
        self.assertEqual(RelatedOfferPublication.objects.count(), 1)

    def test_cards_share_fresh_counts_destination_and_back_scope(self):
        from urllib.parse import parse_qs, urlsplit

        first = self.allow(self.offer())
        self.allow(self.offer(currency="EUR", price=20))
        filters = {"catalog_1_method": "foliar_spray", "catalog_1_target": str(self.target.pk)}
        response = self.anonymous.get(self.api_url(), filters)
        card = response.json()["blocks"][0]["selection"]["results"][0]
        self.assertEqual(card["market"]["offers"], 2)
        self.assertEqual(card["market"]["sellers"], 1)
        filtered_page = self.anonymous.get(self.path, filters)
        self.assertContains(filtered_page, "Пропозиції (2) · Продавці (1)")
        destination = self.anonymous.get(card["market"]["url"])
        self.assertContains(destination, "Пропозицій: 2 · Продавців: 1")
        back = urlsplit(destination.context["back"])
        self.assertEqual(back.path, self.path)
        self.assertEqual(parse_qs(back.query), {key: [value] for key, value in filters.items()})
        self.assertEqual(back.fragment, "related-catalog-1")
        RelatedOfferPublication.objects.exclude(pk=first.pk).update(enabled=False)
        self.assertContains(self.anonymous.get(card["market"]["url"]), "Пропозицій: 1 · Продавців: 1")
        RelatedOfferPublication.objects.update(enabled=False)
        empty = self.anonymous.get(self.api_url(), filters).json()["blocks"][0]["selection"]["results"][0]
        self.assertEqual(empty["market"], {"offers": 0, "sellers": 0, "url": None})
        self.assertContains(self.anonymous.get(self.path, filters), "Чинних пропозицій немає.")
        self.assertContains(self.anonymous.get(card["market"]["url"]), "Чинних пропозицій продавців поки немає.")
