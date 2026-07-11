from django.urls import path

from api.v1.content.views import CategoryTreeView, CountryListView, PostListCreateView, PostUpdateView

urlpatterns = [
    path("categories/tree/", CategoryTreeView.as_view(), name="content-category-tree"),
    path("countries/", CountryListView.as_view(), name="content-country-list"),
    path("posts/", PostListCreateView.as_view(), name="content-post-list-create"),
    path("posts/<int:pk>/", PostUpdateView.as_view(), name="content-post-detail"),
]
