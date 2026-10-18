"""Owned public projections.

No writes, remote calls or cross-database joins.
"""

import re
import unicodedata
from datetime import timedelta
from html import unescape
from urllib.parse import urlsplit

from django.conf import settings
from django.db.models import Exists, OuterRef, Prefetch
from django.urls import reverse
from django.utils import timezone
from django.utils.html import strip_tags

from core.adverts.models import Advert
from core.companies.market import market_offers, summarize_offers
from core.companies.models import Company
from core.events.models import Event
from core.posts.crop_hub import public_categories, public_posts
from core.posts.models import Post

from .models import ResourceType


def plain(value):
    return " ".join(unescape(strip_tags(value or "")).split())


def normalize(value):
    value = unicodedata.normalize("NFKC", value or "").casefold()
    value = re.sub(r"[’‘`ʼ]", "'", value)
    value = re.sub(r"[‐‑–—]", "-", value)
    return " ".join(value.split())


def local_url(value):
    try:
        parsed = urlsplit(value or "")
    except ValueError:
        return False
    return bool(
        value
        and value.startswith("/")
        and not value.startswith("//")
        and not parsed.netloc
        and not parsed.scheme
        and "\\" not in value
        and not any(ord(char) < 32 for char in value)
    )


def search_offers():
    return market_offers().filter(post__in=public_posts(), price_updated_at__lte=timezone.now())


def eligible_sources(*, archive=False):
    """Applied in SQL before counts and pagination, even if the worker is
    down."""
    now = timezone.now()
    categories = public_categories()
    return {
        ResourceType.POST: public_posts(),
        ResourceType.CATEGORY: categories.exclude(absolute_url__isnull=True)
        .exclude(absolute_url="")
        .filter(level__gt=0),
        ResourceType.ADVERT: Advert.objects.filter(
            is_active=True, updated__gte=now - timedelta(days=settings.ADVERT_ACTIVE_DAYS)
        ).filter(category_id__isnull=True)
        | Advert.objects.filter(
            is_active=True, updated__gte=now - timedelta(days=settings.ADVERT_ACTIVE_DAYS), category__in=categories
        ),
        ResourceType.MARKET: public_posts().filter(pk__in=search_offers().values("post_id")),
        ResourceType.COMPANY: Company.objects.filter(active=True),
        ResourceType.EVENT: Event.objects.filter(status=True, **({"stop__lt": now} if archive else {"stop__gte": now})),
    }


def post_url(post):
    # Derive from current taxonomy; never call get_absolute_url(), which may save.
    if post.absolute_url:
        return post.absolute_url
    if not post.rubric.parent_id:
        return ""
    return reverse("post-detail", args=[post.rubric.parent.slug, post.rubric.slug, post.slug, post.pk])


def projections(kind):
    """Index potential public content; runtime selectors enforce time
    boundaries."""
    if kind in (ResourceType.POST, ResourceType.MARKET):
        posts = Post.objects.filter(status=True).select_related("rubric__parent").prefetch_related("tags")
        if kind == ResourceType.MARKET:
            posts = posts.filter(pk__in=search_offers().values("post_id")).prefetch_related(
                Prefetch("product_set", queryset=search_offers(), to_attr="search_eligible_offers")
            )
        for post in posts.iterator(chunk_size=200):
            aliases = [tag.name for tag in post.tags.all()]
            if kind == ResourceType.MARKET:
                aliases.extend(offer.name for offer in post.search_eligible_offers)
            yield document(
                kind,
                post.pk,
                post.title,
                reverse("market:variety", args=[post.pk]) if kind == ResourceType.MARKET else post_url(post),
                post.text,
                " ".join(value for value in aliases if value),
                post.rubric.value,
            )
    elif kind == ResourceType.CATEGORY:
        for category in public_categories().filter(level__gt=0).select_related("meta").iterator():
            yield document(
                kind,
                category.pk,
                category.value,
                category.absolute_url,
                category.meta.description if category.meta_id else "",
            )
    elif kind == ResourceType.ADVERT:
        for advert in Advert.objects.filter(is_active=True).select_related("category", "location").iterator():
            yield document(
                kind,
                advert.pk,
                advert.title,
                advert.get_absolute_url(),
                advert.description,
                taxonomy=" ".join(
                    v
                    for v in [
                        advert.category.value if advert.category_id else "",
                        advert.location.value if advert.location_id else "",
                    ]
                    if v
                ),
            )
    elif kind == ResourceType.COMPANY:
        for company in Company.objects.filter(active=True).select_related("location").iterator():
            yield document(
                kind,
                company.pk,
                company.name,
                company.get_absolute_url(),
                company.description,
                taxonomy=company.location.value,
            )
    elif kind == ResourceType.EVENT:
        for event in Event.objects.filter(status=True).select_related("location", "type").iterator():
            yield document(
                kind,
                event.pk,
                event.title,
                event.get_absolute_url(),
                event.text,
                taxonomy=f"{event.type.title} {event.location.value} {event.address}",
            )


def document(kind, source_id, title, url, body="", aliases="", taxonomy=""):
    body = plain(body)
    return {
        "resource_type": kind,
        "source_id": source_id,
        "title": plain(title)[:512],
        "normalized_title": normalize(plain(title))[:512],
        "canonical_url": url or "",
        "summary": body[:300],
        "body": normalize(body),
        "aliases": normalize(aliases),
        "taxonomy": normalize(taxonomy),
    }


def visible_documents(queryset, *, archive=False):
    # Correlated EXISTS avoids materializing all public IDs in Python.
    from django.db.models import Q

    condition = Q(pk__in=[])
    for kind, sources in eligible_sources(archive=archive).items():
        condition |= Q(resource_type=kind) & Q(Exists(sources.filter(pk=OuterRef("source_id"))))
    return queryset.filter(condition)


def hydrate_market(documents):
    """Batch current offers and aggregate currencies independently, only for
    this page."""
    market_ids = [doc.source_id for doc in documents if doc.resource_type == ResourceType.MARKET]
    markets = (
        {
            post.pk: summarize_offers(post)
            for post in Post.objects.filter(pk__in=market_ids).prefetch_related(
                Prefetch(
                    "product_set", queryset=search_offers().order_by("company__name", "pk"), to_attr="market_offers"
                )
            )
        }
        if market_ids
        else {}
    )
    for doc in documents:
        doc.market = markets.get(doc.source_id) if doc.resource_type == ResourceType.MARKET else None
    return documents
