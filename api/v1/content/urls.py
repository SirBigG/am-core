from django.urls import path

from api.v1.content.views import CategoryTreeView, CountryListView, PostListCreateView, PostUpdateView

from .attribute_schema import (
    CategorySchemaView,
    ChoiceDetailView,
    ChoiceListView,
    FieldDetailView,
    FieldListView,
    GroupDetailView,
    GroupListView,
)

urlpatterns = [
    path("categories/<int:pk>/schema/", CategorySchemaView.as_view(), name="content-category-schema"),
    path("attribute-groups/", GroupListView.as_view(), name="content-attribute-groups"),
    path("attribute-groups/<int:pk>/", GroupDetailView.as_view(), name="content-attribute-group"),
    path("attribute-fields/", FieldListView.as_view(), name="content-attribute-fields"),
    path("attribute-fields/<int:pk>/", FieldDetailView.as_view(), name="content-attribute-field"),
    path("attribute-choices/", ChoiceListView.as_view(), name="content-attribute-choices"),
    path("attribute-choices/<int:pk>/", ChoiceDetailView.as_view(), name="content-attribute-choice"),
    path("categories/tree/", CategoryTreeView.as_view(), name="content-category-tree"),
    path("countries/", CountryListView.as_view(), name="content-country-list"),
    path("posts/", PostListCreateView.as_view(), name="content-post-list-create"),
    path("posts/<int:pk>/", PostUpdateView.as_view(), name="content-post-detail"),
]
