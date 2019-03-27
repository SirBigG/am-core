import requests

from django import template
from django.conf import settings

from core.classifier.models import Category

register = template.Library()


@register.inclusion_tag('news/filter_dropdown.html')
def categories_filter():
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    response = requests.get(f'{settings.API_HOST}/categories')
    if response.status_code == 200:
        categories = Category.objects.filter(id__in=response.json()).order_by('value')
    else:
        categories = Category.objects.none()
    return {'categories': categories}
