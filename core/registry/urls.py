from django.urls import path

from core.registry.views import VarietyCategoryListView, VarietyListView

urlpatterns = [
    path("<str:root_slug>/<str:child_slug>/", VarietyListView.as_view(), name="index-parent"),
    path("<str:root_slug>/", VarietyCategoryListView.as_view(), name="index-parent"),
    path("", VarietyCategoryListView.as_view(), name="index"),
]
