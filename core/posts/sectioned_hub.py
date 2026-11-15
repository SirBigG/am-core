"""Sectioned landing pages assembled from admin-owned hub references."""

from urllib.parse import urlencode

from django.db.models import Count, Exists, OuterRef, Subquery

from core.companies.market import crop_market_offers, market_offers, market_posts, summarize_offers
from core.companies.models import Company, CompanyType, Product
from core.posts.category_attribute_filters import apply_category_attribute_filters, build_category_attribute_filters
from core.posts.crop_hub import configured_sections, public_categories, public_posts, subtree


def build_sectioned_hub_context(category, config, params, context):
    sections = configured_sections(category, config)
    varieties = next((item["category"] for item in sections if item["role"] == "varieties"), None)
    # An explicitly configured but hidden/deleted source must not fall back to
    # another catalog. Match the ordinary hub's market policy exactly.
    if config.get("market_category_id"):
        source = public_categories().filter(pk=config["market_category_id"]).first()
        offers = market_offers().filter(category=source) if source else Product.objects.none()
    else:
        offers = crop_market_offers(category, config)
    latest, countries, filters = [], {}, []
    search = params.get("q", "").strip()[:160]
    if varieties:
        catalog = public_posts().filter(subtree(varieties))
        countries = dict(
            catalog.filter(country__isnull=False)
            .order_by("country__value", "country__slug")
            .values_list("country__slug", "country__value")
            .distinct()
        )
        if params.get("country"):
            catalog = catalog.filter(country__slug=params["country"])
        filters = build_category_attribute_filters(varieties, catalog, params)
        catalog = apply_category_attribute_filters(catalog, varieties, params)
        if search:
            catalog = catalog.filter(title__icontains=search)
        latest = list(
            catalog.annotate(has_offers=Exists(offers.filter(post_id=OuterRef("pk")))).order_by("-publish_date", "-pk")[
                :3
            ]
        )

    popular = [
        summarize_offers(post)
        for post in market_posts(offers=offers)
        .filter(pk__in=public_posts())
        .annotate(
            offer_count=Subquery(
                offers.filter(post_id=OuterRef("pk"))
                .order_by()
                .values("post_id")
                .annotate(total=Count("pk"))
                .values("total")
            )
        )
        .order_by("-offer_count", "title", "pk")[:3]
    ]
    companies = (
        Company.objects.filter(active=True, type=CompanyType.SHOP)
        .filter(pk__in=offers.values("company_id"))
        .select_related("location__region")
        .order_by("name", "pk")[:6]
    )
    # Reuse the URL-safe, date-filtered guide dictionaries built by crop_hub;
    # the raw guide query deliberately also serves authorized admin previews.
    guide_url = next((item["url"] for item in sections if item["role"] == "growing"), "")
    if config.get("guide_category_id"):
        guide_url = (
            public_categories().filter(pk=config["guide_category_id"]).values_list("absolute_url", flat=True).first()
            or ""
        )
    return {
        "latest_varieties": latest,
        "catalog_url": varieties.absolute_url if varieties else "",
        "countries": countries,
        "attribute_filters": filters,
        "has_active_filters": any(value for _, values in params.lists() for value in values),
        "variety_search": search,
        "guides": context["growing_guides"],
        "guide_url": guide_url,
        "protection_sections": [item for item in sections if item["role"] in {"diseases", "pests", "protection"}],
        "additional_sections": [item for item in sections if item["role"] == "additional"],
        "popular": popular,
        "companies": companies,
        "market_url": context["marketplace_links"]["offers"],
        "companies_url": context["marketplace_links"]["sellers"],
        "market_query": "" if config.get("market_category_id") else "?" + urlencode({"hub": category.slug}),
    }
