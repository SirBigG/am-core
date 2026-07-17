from dal import autocomplete
from django.views.generic import TemplateView
from mptt.utils import get_cached_trees
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


class DiaryPlantCategoryAutocomplete(autocomplete.Select2QuerySetView):
    """Return diary species categories."""

    def get_queryset(self):
        qs = Category.objects.filter(
            is_active=True,
            parent__is_active=True,
            parent__value="Рослинництво",
        ).order_by("value")

        if self.q:
            qs = qs.filter(value__icontains=self.q)

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
        roots = get_cached_trees(Category.objects.select_related("meta").order_by("tree_id", "lft"))
        roots = [root for root in roots if root.is_active]
        if "slug" in self.kwargs and self.kwargs["slug"]:
            roots = [root for root in roots if root.slug == self.kwargs["slug"]]
            category = roots[0] if roots else None
            if category:
                metadata = {
                    "title": category.value,
                    "description": f"Публікації в категорії {category.value}",
                    "page_title": f"Публікації в категорії {category.value}",
                }
        context["roots"] = sorted(roots, key=lambda category: category.value)
        context["metadata"] = metadata
        return context
