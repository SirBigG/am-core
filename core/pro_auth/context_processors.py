from django.conf import settings


def forum(request):
    forum_base_url = settings.FORUM_BASE_URL
    return {
        "forum_sso_url": settings.FORUM_SSO_URL if request.user.is_authenticated else f"{forum_base_url}/",
    }
