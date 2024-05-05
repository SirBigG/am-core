from django import template

from core.classifier.models import Category

register = template.Library()


@register.simple_tag
def get_root_categories_links():
    categories = Category.objects.filter(level=0, is_active=True).order_by("value")
    return [{"title": category.value, "url": f"/categories/{category.slug}/"} for category in categories]
