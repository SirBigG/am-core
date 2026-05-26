from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def static_push(path):
    return static(path)
