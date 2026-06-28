from django.urls import path

from api.v1.parser.views import (
    ParserSourceFailureView,
    ParserSourceLeaseView,
    ParserSourceListView,
    ParserSourceResultsView,
)

urlpatterns = [
    path("parser/sources/", ParserSourceListView.as_view(), name="parser-source-list"),
    path("parser/sources/<int:pk>/lease/", ParserSourceLeaseView.as_view(), name="parser-source-lease"),
    path("parser/sources/<int:pk>/results/", ParserSourceResultsView.as_view(), name="parser-source-results"),
    path("parser/sources/<int:pk>/failure/", ParserSourceFailureView.as_view(), name="parser-source-failure"),
]
