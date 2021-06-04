from urllib.parse import urlparse

from django import template
from django.conf import settings

from core.classifier.models import Category

from core.posts.models import Post

from core.adverts.models import Advert


register = template.Library()


@register.inclusion_tag('posts/main_menu.html')
def main_menu():
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    return {'roots': Category.objects.filter(level=0, is_active=True).order_by("value")}


@register.inclusion_tag('posts/index_categories.html')
def index_categories():
    """
    :return: rubric roots queryset
    """
    return main_menu()


@register.inclusion_tag('posts/second_menu.html')
def second_menu(parent_slug, current_slug=None):
    return {'menu_items': Category.objects.get(slug=parent_slug).get_children(), 'slug': current_slug}


@register.inclusion_tag('posts/breadcrumbs.html')
def breadcrumbs(category, post_title=None):
    """Breadcrumbs block."""
    return {'items': category.get_ancestors(include_self=True)[1:], 'post_title': post_title}


@register.inclusion_tag('posts/post_adverts_block.html')
def post_adverts(category):
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    return {'adverts': Advert.objects.all().order_by('-created')[:4], "link": f"/adverts/{category.slug}/"}


@register.inclusion_tag('posts/relative_posts.html')
def relative_posts(category):
    return {"posts": Post.objects.prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').filter(rubric=category, status=1).order_by("?")[:4]}


@register.simple_tag
def full_url(url):
    """
    Create full url with hostname.
    :param: absolute url
    :return: full url
    """
    return settings.HOST + url


@register.simple_tag
def thumbnail(photo_obj, width=300, height=None):
    return photo_obj.thumbnail(width, height) if photo_obj else ""


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


@register.filter
def get_domain(link):
    """
    Get domain from start link.
    :param link:
    :return domain:
    """
    return urlparse(link).netloc
