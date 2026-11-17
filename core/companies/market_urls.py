from django.urls import path

from .market_views import MarketListView, MarketSitemapView, MarketVarietyView, market_variety_options
from .related_offer_views import catalog_offers

app_name = "market"
urlpatterns = [
    path("catalog-offers/", catalog_offers, name="related-offers"),
    path("", MarketListView.as_view(), name="list"),
    path("variety-options/", market_variety_options, name="variety-options"),
    path("sitemap.xml", MarketSitemapView.as_view(), name="sitemap"),
    path("variety/<int:pk>/", MarketVarietyView.as_view(), name="variety"),
    path("category/<str:slug>/", MarketListView.as_view(), name="category"),
]
