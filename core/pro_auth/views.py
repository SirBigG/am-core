import os
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import login, logout
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode as django_urlencode
from django.views.decorators.http import require_GET
from django.views.generic import FormView, ListView, TemplateView, UpdateView, View

from core.adverts.forms import AdvertForm
from core.adverts.models import Advert
from core.pro_auth.forms import LoginForm, RegistrationForm, UserChangeForm


class Login(TemplateView):
    template_name = "pro_auth/login.html"
    success_url = "/"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        default_tab = "register" if self.request.resolver_match.url_name == "register" else "login"
        context.setdefault("login_form", kwargs.get("login_form") or LoginForm(request=self.request))
        context.setdefault("register_form", kwargs.get("register_form") or RegistrationForm())
        context.setdefault("active_tab", kwargs.get("active_tab", default_tab))
        return context

    def post(self, request, *args, **kwargs):
        action = request.POST.get("action", "login")
        if action == "register":
            return self.handle_register()
        return self.handle_login()

    def handle_login(self):
        login_form = LoginForm(request=self.request, data=self.request.POST)
        register_form = RegistrationForm()
        if login_form.is_valid():
            login(self.request, login_form.get_user())
            return redirect(self.get_success_url())
        context = self.get_context_data(
            login_form=login_form,
            register_form=register_form,
            active_tab="login",
        )
        return self.render_to_response(context)

    def handle_register(self):
        register_form = RegistrationForm(self.request.POST)
        login_form = LoginForm(request=self.request)
        if register_form.is_valid():
            user = register_form.save()
            login(self.request, user, backend="core.pro_auth.backends.AuthBackend")
            return redirect(self.get_success_url())
        context = self.get_context_data(
            login_form=login_form,
            register_form=register_form,
            active_tab="register",
        )
        return self.render_to_response(context)

    def get_success_url(self):
        return self.request.POST.get("next") or self.request.GET.get("next") or self.success_url


class SocialExistUserLogin(FormView):
    form_class = LoginForm
    template_name = "pro_auth/login.html"

    def form_valid(self, form):
        self.request.session["user_pk"] = form.get_user().pk
        return HttpResponseRedirect(reverse("social:complete", args=(self.kwargs.get("backend_name"),)))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.setdefault("login_form", context.get("form"))
        context.setdefault("register_form", RegistrationForm())
        context.setdefault("active_tab", "login")
        return context


class Logout(View):
    """Redirects to main page if user logout."""

    url = "/"

    def get(self, request):
        next_url = request.GET.get("next") or self.url
        logout(request)
        if request.GET.get("local") or request.GET.get("skip_forum") or not settings.FORUM_LOGOUT_URL:
            return HttpResponseRedirect(next_url)
        redirect_url = request.build_absolute_uri(next_url)
        return HttpResponseRedirect(f"{settings.FORUM_LOGOUT_URL}?{urlencode({'next': redirect_url})}")


class IsAuthenticate(View):
    """Check current session authentication."""

    def get(self, request):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"is_authenticate": 1 if request.user.is_authenticated else 0})
        raise Http404


class ChangeProfileView(FormView):
    form_class = UserChangeForm
    template_name = "pro_auth/profile/change_profile.html"
    success_url = "/profile/change"

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(instance=self.request.user, **self.get_form_kwargs())

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ProfileAdvertListView(ListView):
    template_name = "pro_auth/profile/advert_list.html"
    model = Advert
    ordering = "-updated"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user)


class ProfileAdvertAddView(FormView):
    form_class = AdvertForm
    template_name = "pro_auth/profile/advert_add.html"

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class UpdateProfileAdvertsView(UpdateView):
    form_class = AdvertForm
    template_name = "pro_auth/profile/advert_update.html"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user)

    def get_success_url(self):
        return reverse("pro_auth:profile-adverts")

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class UpdateProfileAdvertsDateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.updated = timezone.now()
        advert.save()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertDeleteView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.delete()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertDeactivateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.deactivate()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertActivateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.activate()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


@require_GET
def social_oidc_begin(request):
    """Start OIDC authorization on the main site by redirecting to the OAuth2
    authorize endpoint.

    This endpoint allows the forum to redirect users to the main site's authorization flow.
    It accepts an optional `next` parameter which will be included in the `state` value so
    the forum knows where to redirect the user after authentication.
    """
    next_url = request.GET.get("next") or "/"
    client_id = os.getenv("FORUM_OIDC_CLIENT_ID", "agromega-forum")
    # The redirect URI must match the one registered for the forum OIDC application.
    redirect_uri = os.getenv("FORUM_OIDC_REDIRECT_URI", f"{settings.FORUM_BASE_URL}/complete/oidc/")
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid profile email",
        "state": next_url,
    }
    authorize_url = f"{settings.SITE_URL}/o/authorize/?{django_urlencode(params)}"
    return redirect(authorize_url)
