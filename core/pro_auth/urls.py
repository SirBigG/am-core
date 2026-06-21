from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from core.pro_auth.views import (
    ChangeProfileView,
    IsAuthenticate,
    Login,
    Logout,
    SocialExistUserLogin,
)

app_name = "pro_auth"

urlpatterns = [
    path("register/social/<str:backend_name>/login/", SocialExistUserLogin.as_view(), name="social-user-exist"),
    path("", include("core.adverts.profile_urls")),
    path("", include("core.diary.profile_urls")),
    path(
        "profile/",
        login_required(TemplateView.as_view(template_name="pro_auth/profile/dashboard.html")),
        name="dashboard",
    ),
    path("profile/change", login_required(ChangeProfileView.as_view()), name="change-profile"),
    path("login/", Login.as_view(), name="login"),
    path("register/", Login.as_view(), name="register"),
    path("logout/", Logout.as_view(), name="logout"),
    path("is-authenticate/", IsAuthenticate.as_view(), name="is_authenticate"),
]
