from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views import View


class SSOStartView(View):
    def get(self, request):
        if request.user.is_authenticated:
            return redirect(f"{settings.FORUM_SITE_URL}/")
        next_url = request.GET.get("next") or f"{settings.FORUM_SITE_URL}/"
        # Start the social auth flow on the forum instance itself so the forum
        # stores the `state` value in the user's session. Build the publicly
        # reachable forum begin URL (served under /forum on the main nginx host)
        # and include an absolute `next` so the forum knows where to return after auth.
        forum_next = next_url if next_url.startswith(("http://", "https://")) else request.build_absolute_uri(next_url)
        forum_begin = f"{settings.FORUM_SITE_URL}/login/oidc/"
        return redirect(f"{forum_begin}?{urlencode({'next': forum_next})}")


class ForumLogoutView(View):
    def get(self, request):
        logout(request)
        next_url = request.GET.get("next") or settings.MAIN_SITE_URL
        return redirect(next_url)


class MainSiteAccountRedirectView(View):
    def get(self, request):
        return redirect(f"{settings.MAIN_SITE_URL}/login/")


class SSOErrorView(View):
    def get(self, request):
        return HttpResponse("Forum sign-in failed. Please return to the main site and try again.", status=403)
