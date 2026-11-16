from django.urls import include, path
from rest_framework.routers import SimpleRouter

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
from .hubs import (
    CategoryPresentationView,
    GuidePlacementViewSet,
    GuideSectionViewSet,
    HubSectionViewSet,
    HubViewSet,
)
from .media import CategoryImagesView, ContentPhotoViewSet
from .product_matching import ProductMatchView
from .taxonomy import CategorySetupDetail, CategorySetupList

hub_router = SimpleRouter()
hub_router.register("hubs", HubViewSet, basename="content-hub")
hub_router.register("hub-sections", HubSectionViewSet, basename="content-hub-section")
hub_router.register("guide-sections", GuideSectionViewSet, basename="content-guide-section")
hub_router.register("guide-placements", GuidePlacementViewSet, basename="content-guide-placement")
hub_router.register("photos", ContentPhotoViewSet, basename="content-photo")

urlpatterns = [
    path("catalog/", include("api.v1.content.catalog.urls")),
    path("products/<int:pk>/match/", ProductMatchView.as_view(), name="content-product-match"),
    path("categories/", CategorySetupList.as_view(), name="content-category-list"),
    path("categories/<int:pk>/", CategorySetupDetail.as_view(), name="content-category-detail"),
    path("categories/<int:pk>/images/", CategoryImagesView.as_view(), name="content-category-images"),
    path("categories/<int:pk>/presentation/", CategoryPresentationView.as_view(), name="content-category-presentation"),
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

urlpatterns += hub_router.urls
