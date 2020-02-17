from django.urls import path

from rest_framework.urlpatterns import format_suffix_patterns

from api.v1.classifiers.views import LocationListView, CategoryListView, CategoriesTreeView


urlpatterns = format_suffix_patterns([
    path('locations/', LocationListView.as_view(), name='location-list'),
    path(r'categories/', CategoryListView.as_view(), name='category-list'),
    path(r'categories/tree/', CategoriesTreeView.as_view(), name='category-tree'),
])
