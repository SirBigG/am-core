from django.conf import settings


def feature_flags(request):
    return {
        "enable_adverts": settings.ENABLE_ADVERTS,
        "enable_internal_adverts": settings.ENABLE_INTERNAL_ADVERTS,
        "enable_analytics": settings.ENABLE_ANALYTICS,
    }
