from django.urls import path

from api.v1.parser.views import (
    ParserCategoryListView,
    ParserCompanyListView,
    ParserPriceHistoryListView,
    ParserProductListView,
    ParserSourceAttemptListView,
    ParserSourceDetailView,
    ParserSourceFailureView,
    ParserSourceLeaseView,
    ParserSourceListView,
    ParserSourceResultsView,
)

urlpatterns = [
    path("parser/companies/", ParserCompanyListView.as_view(), name="parser-company-list"),
    path("parser/categories/", ParserCategoryListView.as_view(), name="parser-category-list"),
    path("parser/sources/", ParserSourceListView.as_view(), name="parser-source-list"),
    path("parser/sources/<int:pk>/", ParserSourceDetailView.as_view(), name="parser-source-detail"),
    path("parser/sources/<int:pk>/lease/", ParserSourceLeaseView.as_view(), name="parser-source-lease"),
    path("parser/sources/<int:pk>/results/", ParserSourceResultsView.as_view(), name="parser-source-results"),
    path("parser/sources/<int:pk>/failure/", ParserSourceFailureView.as_view(), name="parser-source-failure"),
    path("parser/attempts/", ParserSourceAttemptListView.as_view(), name="parser-attempt-list"),
    path("parser/products/", ParserProductListView.as_view(), name="parser-product-list"),
    path("parser/price-history/", ParserPriceHistoryListView.as_view(), name="parser-price-history-list"),
]
