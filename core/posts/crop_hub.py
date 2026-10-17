"""Configured category landing pages.

No crop-specific queries or URL writes. The current database owns site
content; site/locale select configuration and cache namespaces, not
fictitious Post site memberships.
"""

import hashlib
import json
from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.db.models import Count, Exists, Max, Prefetch, Q
from django.urls import reverse
from django.utils import timezone, translation

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.posts.guide_hub import _inactive_category_ancestors, get_public_guide_sections
from core.posts.models import Post

SECTION_LABELS = {
    "varieties": ("Сорти", "Характеристики сортів та матеріали каталогу."),
    "diseases": ("Хвороби", "Ознаки хвороб та матеріали про захист рослин."),
    "pests": ("Шкідники", "Опис шкідників та матеріали про захист рослин."),
    "growing": ("Вирощування та догляд", "Практичні матеріали від підготовки до зберігання."),
}


def hub_config(slug, site=None, locale=None):
    site = str(site if site is not None else getattr(settings, "SITE_ID", "default"))
    locale = locale or translation.get_language() or settings.LANGUAGE_CODE
    site_filter = Q(site__isnull=True)
    if site.isdecimal():
        site_filter |= Q(site_id=int(site))
    hub = (
        CategoryHub.objects.filter(category__slug=slug, is_active=True)
        .filter(site_filter)
        .filter(Q(locale="") | Q(locale=locale))
        .prefetch_related(Prefetch("sections", queryset=CategoryHubSection.objects.filter(is_active=True)))
        .first()
    )
    if hub is None:
        return None
    # Fresh configuration reads are cheap and keep admin edits effective even
    # while expensive aggregates remain cached. No model instances enter cache.
    return {
        "id": hub.pk,
        "category_slug": slug,
        "description": hub.description,
        "guide_category_id": hub.guide_category_id,
        "market_category_id": hub.market_category_id,
        "site_id": hub.site_id,
        "locale": hub.locale,
        "updated": hub.updated.isoformat(),
        "sections": [
            {
                "id": section.pk,
                "category_id": section.category_id,
                "role": section.role,
                "title": section.title,
                "description": section.description,
                "sort_order": section.sort_order,
            }
            for section in hub.sections.all()
        ],
    }


def public_categories():
    return Category.objects.alias(hidden=Exists(_inactive_category_ancestors(""))).filter(hidden=False)


def public_posts():
    return (
        Post.objects.filter(status=True, publish_date__lte=timezone.now())
        .exclude(absolute_url="")
        .alias(hidden=Exists(_inactive_category_ancestors("rubric")))
        .filter(hidden=False)
    )


def subtree(category):
    return Q(rubric__tree_id=category.tree_id, rubric__lft__gte=category.lft, rubric__rght__lte=category.rght)


def configured_sections(category, config):
    """Resolve explicit public category references, in configured order."""
    if not public_categories().filter(pk=category.pk).exists():
        return []
    descendants = {
        item.pk: item
        for item in public_categories()
        .filter(
            pk__in=[section["category_id"] for section in config["sections"]],
        )
        .exclude(tree_id=category.tree_id, lft__lte=category.lft, rght__gte=category.rght)
    }
    result = []
    used = set()
    for section in config["sections"]:
        role = section["role"]
        item = descendants.get(section["category_id"])
        if item is None or item.pk in used or not item.absolute_url:
            continue
        used.add(item.pk)
        label, description = SECTION_LABELS.get(role, (item.value, "Матеріали категорії."))
        result.append(
            {
                "role": role,
                "category": item,
                "label": section["title"] or label,
                "description": section["description"] or description,
                "url": item.absolute_url,
            }
        )
    return result


def hub_market_categories(category, config):
    # Only the explicit variety section is a crop identity, never all descendants
    # (which would include chemicals, pests and disease treatments).
    if config is None:
        return Category.objects.none()
    sections = configured_sections(category, config)
    varieties = next((item["category"] for item in sections if item["role"] == "varieties"), None)
    if varieties is None:
        return Category.objects.none()
    return public_categories().filter(tree_id=varieties.tree_id, lft__gte=varieties.lft, rght__lte=varieties.rght)


def crop_scope_for_post(post):
    """Resolve a catalog article's strict scope outside the one-query market
    link helper.

    Never use the article's title as an inferred crop mapping.
    """
    rubric = Category.objects.get(pk=post.rubric_id)
    hubs = (
        CategoryHub.objects.filter(
            is_active=True,
            sections__is_active=True,
            sections__role="varieties",
            sections__category__tree_id=rubric.tree_id,
            sections__category__lft__lte=rubric.lft,
            sections__category__rght__gte=rubric.rght,
        )
        .select_related("category")
        .order_by("-sections__category__level", "pk")
    )
    for hub in hubs:
        category = hub.category
        config = hub_config(category.slug)
        if config is not None and hub_market_categories(category, config).filter(pk=post.rubric_id).exists():
            return category, config
    return None


def metric(value, label, url):
    return {"value": value, "label": label, "url": url, "available": value is not None}


def _article(post):
    # Avoid storing live model instances/querysets in cache or invoking URL saves.
    return {"id": post.pk, "title": post.title, "url": post.absolute_url, "absolute_url": post.absolute_url}


def _build_context(category, config):
    from core.companies.market import crop_market_offers, market_offers, market_posts
    from core.companies.models import Product
    from core.posts.crop_prices import build_price_overview

    now = timezone.now()
    hub_query = urlencode({"hub": category.slug})
    sections = configured_sections(category, config)
    posts = public_posts()
    knowledge = []
    for section in sections:
        section["value"] = posts.filter(subtree(section["category"])).values("pk").distinct().count()
        knowledge.append(metric(section["value"], section["label"], section["url"]))
    guide_source = config.get("guide_category_id")
    guide_category = category
    if guide_source:
        guide_category = public_categories().filter(pk=guide_source).first()
    guides, represented = [], set()
    if guide_category:
        for section in get_public_guide_sections(guide_category.pk):
            articles = []
            for placement in section.public_articles:
                post = placement.post
                if post.pk in represented or not post.absolute_url or post.publish_date > now:
                    continue
                represented.add(post.pk)
                articles.append(_article(post))
            if articles:
                guides.append({"title": section.title, "articles": articles})
    if guides and not any(item["role"] == "growing" for item in sections):
        knowledge.append(metric(len(represented), "Практичні матеріали", "#growing-guides"))
    varieties = next((item["category"] for item in sections if item["role"] == "varieties"), None)
    widget_configured = bool(config.get("market_category_id"))
    market_category = public_categories().filter(pk=config["market_category_id"]).first() if widget_configured else None
    if widget_configured:
        # Mirror the ordinary category market exactly. Do not reclassify or
        # dedupe products, or change matching/price policy for any market view.
        offers = market_offers().filter(category_id=market_category.pk) if market_category else Product.objects.none()
    else:
        offers = crop_market_offers(category, config)
    totals = offers.aggregate(
        offers=Count("pk"),
        sellers=Count("company_id", distinct=True),
        varieties=Count("post_id", distinct=True),
        updated=Max("price_updated_at"),
    )
    updated = totals["updated"]
    featured = []
    if varieties:
        featured_posts = list(posts.filter(subtree(varieties)).exclude(pk__in=represented).order_by("title", "pk")[:6])
        market_post_ids = set(
            offers.filter(post_id__in=[post.pk for post in featured_posts]).values_list("post_id", flat=True)
        )
        for post in featured_posts:
            item = _article(post)
            item["market_url"] = (
                reverse("market:variety", args=[post.pk]) + ("" if widget_configured else "?" + hub_query)
                if post.pk in market_post_ids
                else ""
            )
            featured.append(item)
            represented.add(post.pk)
    # Additional articles exclude catalogs already represented by navigation,
    # as well as placements and featured entries.
    additional = posts.filter(subtree(category)).exclude(pk__in=represented)
    for section in sections:
        additional = additional.exclude(subtree(section["category"]))
    additional = [_article(post) for post in additional.order_by("-publish_date", "pk")[:6]]
    if widget_configured:
        market_url = reverse("market:category", args=[market_category.slug]) if market_category else ""
        company_url = (
            reverse("companies:list") + "?" + urlencode({"category": market_category.slug}) if market_category else ""
        )
    else:
        market_url = reverse("market:list") + "?" + hub_query
        company_url = reverse("companies:list") + "?" + hub_query
    market_stats = [
        metric(totals["offers"], "Пропозиції" if widget_configured else "Унікальні пропозиції продавців", market_url),
        metric(
            totals["sellers"],
            "Компанії з пропозиціями" if widget_configured else "Продавці з перевіреними пропозиціями",
            company_url,
        ),
        metric(totals["varieties"], "Сорти з пропозиціями", market_url),
    ]
    price_overview = build_price_overview(offers, now)
    market_widget = None
    if market_category:
        preview = market_posts(offers=offers).filter(rubric_id=market_category.pk)[:6]
        market_widget = {
            "category_id": market_category.pk,
            "category_name": market_category.value,
            "url": market_url,
            "stats": market_stats,
            "items": [
                {
                    "id": post.pk,
                    "title": post.title,
                    "url": reverse("market:variety", args=[post.pk]),
                    "offer_count": len(post.market_offers),
                    "seller_count": len({offer.company_id for offer in post.market_offers}),
                }
                for post in preview
            ],
            "updated_at": updated,
        }
    groups = []
    if varieties:
        groups.append({"label": "Пропозиції сортів каталогу", "url": market_url})
    description = config.get("description") or (
        f"{category.value}: сорти, практичні матеріали та пропозиції Агромаркету."
        if widget_configured
        else f"{category.value}: сорти, практичні матеріали та перевірені пропозиції продавців AgroMega."
    )
    navigation = [{key: value for key, value in item.items() if key != "category"} for item in sections]
    return {
        "title": (category.meta.title if category.meta else "")
        or f"{category.value} — знання та пропозиції | AgroMega",
        "description": description,
        "knowledge_stats": knowledge,
        "knowledge_sections": navigation,
        "growing_guides": guides,
        "featured_varieties": featured,
        "additional_articles": additional,
        "more_articles_url": next((item["url"] for item in sections if item["role"] == "growing"), ""),
        "market_widget_configured": widget_configured,
        "market_widget": market_widget,
        "market_stats": market_stats,
        "market_groups": groups,
        "data_updated_at": updated,
        "marketplace_links": {"offers": market_url, "sellers": company_url},
        "price_overview": price_overview,
        "price_summary": {
            "available": False,
            "reason": "Недостатньо порівнюваних пропозицій",
            "detail": "У записах немає перевіреної маси пакування та призначення товару. Ціни за кілограм не розраховуються.",
            "currency": "UAH",
            "unit": None,
            "observation_count": 0,
            "seller_count": 0,
            "updated_at": None,
            "method": None,
            "minimum_offers": settings.CROP_HUB_PRICE_MIN_OFFERS,
            "minimum_sellers": settings.CROP_HUB_PRICE_MIN_SELLERS,
        },
        "object_list": featured + additional,
        "primary_actions": [item for item in navigation if item["role"] in ("varieties", "growing")],
    }


def build_crop_hub_context(category, site=None, locale=None, config=None):
    site = str(site if site is not None else getattr(settings, "SITE_ID", "default"))
    locale = locale or translation.get_language() or settings.LANGUAGE_CODE
    if config is None:
        config = hub_config(category.slug, site, locale)
    if config is None:
        return None
    digest = hashlib.sha256(
        json.dumps(
            {
                "config": config,
                "site": site,
                "locale": locale,
                "host": settings.HOST,
                "database": settings.DATABASES["default"]["NAME"],
                "fresh_days": min(settings.PRODUCT_PRICE_FRESH_DAYS, settings.CROP_HUB_FRESH_DAYS),
                "thresholds": [settings.CROP_HUB_PRICE_MIN_OFFERS, settings.CROP_HUB_PRICE_MIN_SELLERS],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    key = f"crop-hub:v5:{category.pk}:{digest}"
    context = cache.get(key)
    if context is None:
        context = _build_context(category, config)
        # Short lifetime bounds eligibility/freshness drift, even with future
        # offers or publication dates. No new cache infrastructure required.
        cache.set(key, context, max(0, min(settings.CROP_HUB_CACHE_TTL, 300)))
    return {**context, "category": category, "site": site, "locale": locale}
