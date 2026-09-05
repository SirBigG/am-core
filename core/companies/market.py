"""Catalog identity and fresh seller offers for the public market."""

from datetime import timedelta

from django.conf import settings
from django.db.models import Exists, F, OuterRef, Prefetch, Q
from django.urls import reverse
from django.utils import timezone

from core.classifier.models import Category
from core.posts.models import Post

from .models import Product


def publication_market_context(post, registry_variety_exists=False):
    """Post is the market identity; registry Variety has a separate primary
    key.

    Keep legacy related products only outside registry/market-linked identities.
    Do not cache eligibility: price expiry and parser/admin changes apply on the
    next render. Both checks use EXISTS, never materializing seller offers.
    """
    can_show = market_offers().filter(post_id=post.pk).exists()
    replace_related_products = (
        can_show
        or registry_variety_exists
        or Product.objects.filter(post_id=post.pk, category_id=post.rubric_id).exists()
    )
    return {
        "entity_name": post.title,
        "market_url": reverse("market:variety", args=[post.pk]),
        "can_show": can_show,
        "post_id": post.pk,
        "entity_id": post.pk,
        "replace_related_products": replace_related_products,
    }


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


def market_posts(region=""):
    offers = market_offers()
    if region:
        offers = offers.filter(company__location__region_id=region)
    return (
        Post.objects.filter(status=True, rubric__is_active=True)
        .annotate(has_offers=Exists(offers.filter(post_id=OuterRef("pk"))))
        .filter(has_offers=True)
        .select_related("rubric")
        .prefetch_related(
            Prefetch("product_set", queryset=offers.order_by("company__name", "pk"), to_attr="market_offers"),
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
