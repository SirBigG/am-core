"""Catalog identity and fresh seller offers for the public market."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Prefetch, Q
from django.utils import timezone

from core.classifier.models import Category
from core.posts.models import Photo, Post

from .models import Product


def market_offers():
    return (
        Product.objects.filter(
            active=True,
            company__active=True,
            post__status=True,
            post__rubric__is_active=True,
            category_id=F("post__rubric_id"),
            price_updated_at__gte=timezone.now() - timedelta(days=settings.PRODUCT_PRICE_FRESH_DAYS),
        )
        .filter(Q(price__gt=0) | Q(price__isnull=True, min_price__gt=0))
        .select_related("company", "company__location")
    )


def market_categories():
    return (
        Category.objects.filter(is_active=True)
        .annotate(has_offers=Exists(market_offers().filter(category_id=OuterRef("pk"))))
        .filter(has_offers=True)
        .order_by("value")
    )


def market_posts():
    return (
        Post.objects.filter(status=True, rubric__is_active=True)
        .annotate(has_offers=Exists(market_offers().filter(post_id=OuterRef("pk"))))
        .filter(has_offers=True)
        .select_related("rubric")
        .prefetch_related(
            Prefetch("photo", queryset=Photo.objects.order_by("pk"), to_attr="prefetched_photos"),
            Prefetch("product_set", queryset=market_offers().order_by("company__name", "pk"), to_attr="market_offers"),
        )
        .order_by("title", "pk")
    )


def summarize_offers(post):
    prices = {}
    for offer in post.market_offers:
        lower = offer.price if offer.price is not None else offer.min_price
        upper = lower if offer.price is not None else max(lower, offer.max_price or lower)
        currency = offer.currency or ""
        bucket = prices.setdefault(
            currency, {"min": lower, "max": upper, "currency": offer.get_currency_display() or "Валюта не вказана"}
        )
        bucket["min"] = min(bucket["min"], lower)
        bucket["max"] = max(bucket["max"], upper)
        offer.market_price_min, offer.market_price_max = lower, upper
    post.market_prices = list(prices.values())
    post.market_offer_count = len(post.market_offers)
    post.market_seller_count = len({offer.company_id for offer in post.market_offers})
    return post
