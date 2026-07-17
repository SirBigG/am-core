from django.conf import settings
from django.core.cache import cache

from core.classifier.models import Category

ROOT_CATEGORY_LINKS_CACHE_KEY = "public_root_category_links_v1"
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
        links = [
            {"title": title, "url": f"/categories/{slug}/"}
            for title, slug in Category.objects.filter(level=0, is_active=True)
            .order_by("value")
            .values_list("value", "slug")
        ]
        cache.set(ROOT_CATEGORY_LINKS_CACHE_KEY, links, ROOT_CATEGORY_LINKS_CACHE_TTL)
    return {"root_category_links": links}
