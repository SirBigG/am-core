from dal import autocomplete
from django.views.generic import TemplateView
from taggit.models import Tag

from core.classifier.models import Category, Location


class LocationAutocomplete(autocomplete.Select2QuerySetView):
    """Return locations queryset."""

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


class CategoriesIndex(TemplateView):
    template_name = "categories.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        metadata = {
            "title": "Категорії",
            "description": "Список доступних категорій.",
            "page_title": "Публікації за категоріями",
        }
        qs = Category.objects.filter(level=0, is_active=True)
        if "slug" in self.kwargs and self.kwargs["slug"]:
            qs = qs.filter(slug=self.kwargs["slug"])
            category = qs.first()
            if category:
                metadata = {
                    "title": category.value,
                    "description": f"Публікації в категорії {category.value}",
                    "page_title": f"Публікації в категорії {category.value}",
                }
        context["roots"] = qs.order_by("value")
        context["metadata"] = metadata
        return context
