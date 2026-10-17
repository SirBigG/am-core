from django.conf import settings
from django.core.cache import cache

from core.classifier.models import Category

ROOT_CATEGORY_LINKS_CACHE_KEY = "public_root_category_links_v2"
ROOT_CATEGORY_LINKS_CACHE_TTL = 3600


def feature_flags(request):
    return {
        "enable_adverts": settings.ENABLE_ADVERTS,
        "enable_internal_adverts": settings.ENABLE_INTERNAL_ADVERTS,
        "enable_analytics": settings.ENABLE_ANALYTICS,
    }


def public_navigation(request):
    links = cache.get(ROOT_CATEGORY_LINKS_CACHE_KEY)
    if links is None:
        categories = list(
            Category.objects.filter(is_active=True, level__lte=1)
            .order_by("value", "pk")
            .values("pk", "parent_id", "level", "value", "slug", "absolute_url")
        )
        children = {}
        for category in categories:
            if category["level"] == 1:
                children.setdefault(category["parent_id"], []).append(
                    {"title": category["value"], "url": category["absolute_url"] or f"/{category['slug']}/"}
                )
        links = [
            {
                "title": category["value"],
                "url": f"/categories/{category['slug']}/",
                "children": children.get(category["pk"], []),
            }
            for category in categories
            if category["level"] == 0
        ]
        cache.set(ROOT_CATEGORY_LINKS_CACHE_KEY, links, ROOT_CATEGORY_LINKS_CACHE_TTL)
    return {"root_category_links": links}
