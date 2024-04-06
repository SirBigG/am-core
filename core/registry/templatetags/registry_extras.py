from django import template

from core.registry.models import VarietyCategory

register = template.Library()


@register.inclusion_tag("registry/index.html")
def index_registry():
    """
    :return: rubric roots queryset
    """
    return {"roots": VarietyCategory.objects.filter(level=0).order_by("title")}


@register.inclusion_tag("registry/breadcrumbs.html")
def registry_breadcrumbs(category):
    """Breadcrumbs block."""
    if not category:
        return {"items": []}
    return {"items": category.get_ancestors(include_self=True).values("title", "absolute_url")}
