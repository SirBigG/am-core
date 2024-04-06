from itertools import groupby

from django.http import Http404
from django.views.generic import ListView, TemplateView

from core.registry.models import Variety, VarietyCategory


class VarietyCategoryListView(ListView):
    model = VarietyCategory
    template_name = "registry/index.html"

    def get_queryset(self):
        if self.kwargs.get("root_slug"):
            return VarietyCategory.objects.filter(parent__slug=self.kwargs.get("root_slug")).order_by("title")
        return VarietyCategory.objects.filter(level=0).order_by("title")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["category"] = None
        if self.kwargs.get("root_slug"):
            context["category"] = VarietyCategory.objects.filter(slug=self.kwargs.get("root_slug")).first()
        return context

    def get_template_names(self):
        if self.kwargs.get("root_slug"):
            return "registry/categories.html"
        return self.template_name


class VarietyListView(TemplateView):
    template_name = "registry/varieties.html"

    def get_context_data(self, **kwargs):
        category = VarietyCategory.objects.select_related("meta").filter(slug=self.kwargs["child_slug"]).first()
        if category is None:
            raise Http404
        for i in Variety.objects.filter(category_id=category.id):
            i.save()
        posts = Variety.objects.filter(category_id=category.id).values(
            "title", "publication__absolute_url", "original_country__short_slug"
        )
        posts = [
            [key, list(g)] for key, g in groupby(sorted(posts, key=lambda x: x["title"]), key=lambda x: x["title"][0])
        ]
        return {"posts": posts, "category": category, "view": self, "request": self.request}
