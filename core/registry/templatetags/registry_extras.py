from django import template

from core.registry.models import Variety, VarietyCategory

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


@register.inclusion_tag("registry/table.html")
def variety_item_table(post_id):
    """Varieties table."""
    variety = (
        Variety.objects.select_related("original_country")
        .select_related("applicant")
        .select_related("owner")
        .select_related("breeder")
        .filter(publication_id=post_id)
        .first()
    )
    return {"variety": variety}
