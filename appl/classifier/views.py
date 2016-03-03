# -*- coding: utf-8 -*-

from dal import autocomplete

from appl.classifier.models import Location


class LocationAutocomplete(autocomplete.Select2QuerySetView):
    """
    Return locations queryset.
    """
    def get_queryset(self):
        qs = Location.objects.all()
        if self.q:
            qs = qs.filter(value__istartswith=self.q)
        return qs
