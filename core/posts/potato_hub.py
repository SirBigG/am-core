"""Display data for the potato category landing page."""

from urllib.parse import urlencode

from django.db.models import Count, Exists, OuterRef, Subquery
from django.urls import reverse

from core.companies.market import market_offers, market_posts, summarize_offers
from core.companies.models import Company, CompanyType, Product
from core.posts.category_attribute_filters import apply_category_attribute_filters, build_category_attribute_filters
from core.posts.crop_hub import public_categories, public_posts
from core.posts.guide_hub import get_public_guide_sections

POTATO_PATH = "/kartoplya/"
VARIETY_SLUG = "kartoplia-sorty"
GUIDE_SLUG = "vyroshchuvannia-i-dohliad-kartopli"


def build_potato_sections(category, params, fallback_guides, knowledge_sections):
    children = {child.slug: child for child in public_categories().filter(parent=category)}
    varieties = children.get(VARIETY_SLUG)
    guide = children.get(GUIDE_SLUG)
    offers = market_offers().filter(category=varieties) if varieties else Product.objects.none()
    latest, countries, filters = [], {}, []
    search = params.get("q", "").strip()[:160]
    if varieties:
        catalog = public_posts().filter(rubric=varieties)
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
            catalog.annotate(has_offers=Exists(offers.filter(post_id=OuterRef("pk"))))
            .order_by("-publish_date", "-pk")[:3]
        )

    popular = [
        summarize_offers(post)
        for post in market_posts(offers=offers)
        .filter(pk__in=public_posts())
        .annotate(offer_count=Subquery(
            offers.filter(post_id=OuterRef("pk")).order_by().values("post_id").annotate(total=Count("pk")).values("total")
        ))
        .order_by("-offer_count", "title", "pk")[:3]
    ] if varieties else []
    companies = (
        Company.objects.filter(active=True, type=CompanyType.SHOP)
        .filter(Exists(Product.objects.filter(company_id=OuterRef("pk"), category=varieties, active=True)))
        .select_related("location__region")
        .order_by("?")[:6]
    ) if varieties else []
    return {
        "latest_varieties": latest,
        "catalog_url": varieties.absolute_url if varieties else next(
            (section["url"] for section in knowledge_sections if section["role"] == "varieties"), ""
        ),
        "countries": countries,
        "attribute_filters": filters,
        "has_active_filters": any(value for _, values in params.lists() for value in values),
        "variety_search": search,
        "guide_sections": get_public_guide_sections(guide.pk) if guide else [],
        "fallback_guides": fallback_guides if not guide else [],
        "popular": popular,
        "companies": companies,
        "market_url": reverse("market:category", args=[VARIETY_SLUG]),
        "companies_url": reverse("companies:list") + "?" + urlencode({"category": VARIETY_SLUG}),
    }
