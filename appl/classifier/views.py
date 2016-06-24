from __future__ import unicode_literals

from dal import autocomplete

from appl.classifier.models import Location
from appl.classifier.serializers import LocationSerializer

from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination


class LocationAutocomplete(autocomplete.Select2QuerySetView):
    """
    Return locations queryset.
    """
    def get_queryset(self):
        qs = Location.objects.all()
        if self.q:
            qs = qs.filter(value__istartswith=self.q)
        return qs


class LocationPagination(PageNumberPagination):
    page_size = 10


class LocationListView(ListAPIView):
    serializer_class = LocationSerializer
    pagination_class = LocationPagination

    def get_queryset(self):
        qs = Location.objects.all()
        loc = self.request.query_params.get('loc', None)
        if loc:
            qs = qs.filter(value__istartswith=loc)
        return qs
