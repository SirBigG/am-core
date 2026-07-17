from django import template
from django.conf import settings

from core.classifier.models import Category
from core.news.client import fetch_json

register = template.Library()


@register.inclusion_tag("news/filter_dropdown.html")
def categories_filter():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    status_code, category_ids = fetch_json(f"{settings.API_HOST}/categories")
    if status_code == 200:
        categories = Category.objects.filter(id__in=category_ids).order_by("value")
    else:
        categories = Category.objects.none()
    return {"categories": categories}


@register.filter
def multiply(value, arg):
    return value * arg
