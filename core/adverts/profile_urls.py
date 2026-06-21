from django.contrib.auth.decorators import login_required
from django.urls import path

from core.adverts.views import (
    AdvertActivateView,
    AdvertDeactivateView,
    AdvertDeleteView,
    ProfileAdvertAddView,
    ProfileAdvertListView,
    UpdateProfileAdvertsDateView,
    UpdateProfileAdvertsView,
)

urlpatterns = [
    path(
        "profile/adverts/<int:pk>/update-date/",
        login_required(UpdateProfileAdvertsDateView.as_view()),
        name="profile-adverts-update-date",
    ),
    path("profile/adverts/<int:pk>/delete/", login_required(AdvertDeleteView.as_view()), name="profile-adverts-delete"),
    path(
        "profile/adverts/<int:pk>/deactivate/",
        login_required(AdvertDeactivateView.as_view()),
        name="profile-adverts-deactivate",
    ),
    path(
        "profile/adverts/<int:pk>/activate/",
        login_required(AdvertActivateView.as_view()),
        name="profile-adverts-activate",
    ),
    path("profile/adverts/create", login_required(ProfileAdvertAddView.as_view()), name="profile-adverts-create"),
    path(
        "profile/adverts/update/<int:pk>",
        login_required(UpdateProfileAdvertsView.as_view()),
        name="profile-adverts-update",
    ),
    path("profile/adverts", login_required(ProfileAdvertListView.as_view()), name="profile-adverts"),
]
