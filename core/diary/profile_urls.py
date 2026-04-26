from django.contrib.auth.decorators import login_required
from django.urls import path

from core.diary.views import (
    AddDiaryItemView,
    AddDiaryView,
    DiaryDeleteView,
    DiaryItemDeleteView,
    ProfileDiaryDetailView,
    ProfileDiaryListView,
    UpdateDiaryItemView,
    UpdateProfileDiaryView,
)

urlpatterns = [
    path(
        "profile/diary/item/add/<int:diary_id>",
        login_required(AddDiaryItemView.as_view()),
        name="profile-diary-item-add",
    ),
    path(
        "profile/diary/item/<int:pk>/delete/",
        login_required(DiaryItemDeleteView.as_view()),
        name="profile-diary-item-delete",
    ),
    path(
        "profile/diary/item/<int:pk>/update/",
        login_required(UpdateDiaryItemView.as_view()),
        name="profile-diary-item-update",
    ),
    path(
        "profile/diary/<int:pk>",
        login_required(ProfileDiaryDetailView.as_view()),
        name="profile-diary-detail",
    ),
    path(
        "profile/diary/<int:pk>/delete/",
        login_required(DiaryDeleteView.as_view()),
        name="profile-diary-delete",
    ),
    path(
        "profile/diary/update/<int:pk>",
        login_required(UpdateProfileDiaryView.as_view()),
        name="profile-diary-update",
    ),
    path("profile/diary/add", login_required(AddDiaryView.as_view()), name="profile-diary-add"),
    path("profile/diary", login_required(ProfileDiaryListView.as_view()), name="profile-diary-list"),
]
