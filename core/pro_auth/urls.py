from django.contrib.auth.decorators import login_required
from django.urls import path
from django.views.generic import TemplateView

from core.pro_auth.views import (
    AddDiaryItemView,
    AddDiaryView,
    AdvertActivateView,
    AdvertDeactivateView,
    AdvertDeleteView,
    ChangeProfileView,
    IsAuthenticate,
    Login,
    Logout,
    ProfileAdvertAddView,
    ProfileAdvertListView,
    ProfileDiaryDetailView,
    ProfileDiaryListView,
    SocialExistUserLogin,
    UpdateProfileAdvertsDateView,
    UpdateProfileAdvertsView,
    UpdateProfileDiaryView,
)

app_name = "pro_auth"

urlpatterns = [
    path("register/social/<str:backend_name>/login/", SocialExistUserLogin.as_view(), name="social-user-exist"),
    path(
        "profile/",
        login_required(TemplateView.as_view(template_name="pro_auth/profile/dashboard.html")),
        name="dashboard",
    ),
    path(
        "profile/diary/item/add/<int:diary_id>",
        login_required(AddDiaryItemView.as_view()),
        name="profile-diary-item-add",
    ),
    path("profile/diary/<int:pk>", login_required(ProfileDiaryDetailView.as_view()), name="profile-diary-detail"),
    path(
        "profile/diary/update/<int:pk>", login_required(UpdateProfileDiaryView.as_view()), name="profile-diary-update"
    ),
    path("profile/diary/add", login_required(AddDiaryView.as_view()), name="profile-diary-add"),
    path("profile/diary", login_required(ProfileDiaryListView.as_view()), name="profile-diary-list"),
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
    path("logout/", Logout.as_view(), name="logout"),
    path("is-authenticate/", IsAuthenticate.as_view(), name="is_authenticate"),
]
