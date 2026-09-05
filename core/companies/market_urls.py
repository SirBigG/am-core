from django.urls import path

from .market_views import MarketListView, MarketSitemapView, MarketVarietyView

app_name = "market"
urlpatterns = [
    path("", MarketListView.as_view(), name="list"),
    path("sitemap.xml", MarketSitemapView.as_view(), name="sitemap"),
    path("variety/<int:pk>/", MarketVarietyView.as_view(), name="variety"),
    path("category/<str:slug>/", MarketListView.as_view(), name="category"),
]
