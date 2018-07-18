from django import template
from django.conf import settings
from django.templatetags.static import static

from core.classifier.models import Category


register = template.Library()


@register.inclusion_tag('posts/main_menu.html')
def main_menu():
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    roots = Category.objects.filter(level=0).order_by("value")
    return {'roots': roots}


@register.inclusion_tag('posts/index_categories.html')
def index_categories():
    """
    :return: rubric roots queryset
    """
    return main_menu()


@register.inclusion_tag('posts/second_menu.html')
def second_menu(parent_slug, current_slug=None):
    parent = Category.objects.get(slug=parent_slug)
    return {'menu_items': parent.get_children(), 'slug': current_slug}


@register.inclusion_tag('posts/breadcrumbs.html')
def breadcrumbs(category, post_title=None):
    """Breadcrumbs block."""
    return {'items': category.get_ancestors(include_self=True)[1:], 'post_title': post_title}


@register.simple_tag
def full_url(url):
    """
    Create full url with hostname.
    :param: absolute url
    :return: full url
    """
    return settings.HOST + url


@register.simple_tag
def thumbnail(photo_obj, width=300, height=200):
    if photo_obj:
        return photo_obj.thumbnail(width, height)
    return ''


# ####################    Filters    ################### #

def grouped(l, n):
    # Yield successive n-sized chunks from l.
    for i in range(0, len(l), n):
        yield l[i:i+n]


@register.filter
def group_by(value, arg):
    """
    For grouping iterable items in groups by arg size.
    :param value: iterable,
    :param arg: int
    :return iterator
    """
    return grouped(value, arg)


@register.filter
def times(number):
    """
    For using range function in templatetags.
    :param number: int
    :return range obj:
    """
    return range(1, number+1)


@register.simple_tag
def static_version(path):
    """
    Add version end to static path.
    :param path: path to static file
    :return: full static file path with version
    """
    version = getattr(settings, 'MEDIA_VERSION', '')
    _path = static(path)
    if version:
        _path = '{0}?{1}'.format(_path, version)
    return _path
