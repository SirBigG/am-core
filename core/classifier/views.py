from dal import autocomplete

from core.classifier.models import Location

from taggit.models import Tag


class LocationAutocomplete(autocomplete.Select2QuerySetView):
    """
    Return locations queryset.
    """
    def get_queryset(self):
        qs = Location.objects.prefetch_related("region", "area").all()
        if self.q:
            qs = qs.filter(value__istartswith=self.q)
        return qs


class TagAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        # Don't forget to filter out results depending on the visitor !
        if not self.request.user.is_authenticated:
            return Tag.objects.none()

        qs = Tag.objects.all()

        if self.q:
            qs = qs.filter(name__istartswith=self.q)

        return qs
