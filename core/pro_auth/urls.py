from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic import TemplateView

from core.pro_auth.views import (
    AdvertActivateView,
    AdvertDeactivateView,
    AdvertDeleteView,
    ChangeProfileView,
    IsAuthenticate,
    Login,
    Logout,
    ProfileAdvertAddView,
    ProfileAdvertListView,
    SocialExistUserLogin,
    UpdateProfileAdvertsDateView,
    UpdateProfileAdvertsView,
)

app_name = "pro_auth"

urlpatterns = [
    path("register/social/<str:backend_name>/login/", SocialExistUserLogin.as_view(), name="social-user-exist"),
    path("", include("core.diary.profile_urls")),
    path(
        "profile/",
        login_required(TemplateView.as_view(template_name="pro_auth/profile/dashboard.html")),
        name="dashboard",
    ),
    path("profile/change", login_required(ChangeProfileView.as_view()), name="change-profile"),
    path(
        "profile/adverts/<int:pk>/update-date/",
        login_required(UpdateProfileAdvertsDateView.as_view()),
        name="profile-adverts-update-date",
    ),
    path("profile/adverts/<int:pk>/delete/", AdvertDeleteView.as_view(), name="profile-adverts-delete"),
    path("profile/adverts/<int:pk>/deactivate/", AdvertDeactivateView.as_view(), name="profile-adverts-deactivate"),
    path("profile/adverts/<int:pk>/activate/", AdvertActivateView.as_view(), name="profile-adverts-activate"),
    path("profile/adverts/create", login_required(ProfileAdvertAddView.as_view()), name="profile-adverts-create"),
    path(
        "profile/adverts/update/<int:pk>",
        login_required(UpdateProfileAdvertsView.as_view()),
        name="profile-adverts-update",
    ),
    path("profile/adverts", login_required(ProfileAdvertListView.as_view()), name="profile-adverts"),
    path("login/", Login.as_view(), name="login"),
    path("register/", Login.as_view(), name="register"),
    path("logout/", Logout.as_view(), name="logout"),
    path("is-authenticate/", IsAuthenticate.as_view(), name="is_authenticate"),
]
