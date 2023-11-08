from pathlib import Path
from urllib.parse import urlparse

from PIL import Image
from django import template
from django.conf import settings
from django.urls import reverse

from core.classifier.models import Category

from core.posts.models import Post, Photo

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
    return {'menu_items': Category.objects.get(slug=parent_slug).get_children().values(
        "slug", "value", "absolute_url"), 'slug': current_slug}


@register.inclusion_tag('posts/breadcrumbs.html')
def breadcrumbs(category, post_title=None):
    """Breadcrumbs block."""
    return {'items': category.get_ancestors(include_self=True).values("value", "absolute_url")[1:],
            'post_title': post_title}


@register.inclusion_tag('posts/post_adverts_block.html')
def post_adverts():
    """
    Creating main page menu.
    :return: rubric roots queryset
    """
    context = {'adverts': Advert.objects.values("title", "image", "pk")[:4]}
    for advert in context["adverts"]:
        advert["url"] = reverse('adverts:detail', kwargs={'pk': advert["pk"]})
        if advert["image"]:
            advert["image"] = thumbnail_path(settings.MEDIA_ROOT + "/" + advert["image"], 200, 150)
    return context


@register.inclusion_tag('posts/relative_posts.html')
def relative_posts(category_id):
    context = {"posts": Post.objects.filter(
        rubric_id=category_id, status=True).values("id", "title", "absolute_url", "photo__image").order_by("?")[:4]}
    for post in context["posts"]:
        if post["photo__image"]:
            post["photo__image"] = thumbnail_path(settings.MEDIA_ROOT + "/" + post["photo__image"], 200, 150)
    return context


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


@register.simple_tag
def thumbnail_path(path, width=300, height=None):
    return thumbnail_from_path(path, width, height) if path else ""


# ####################    Filters    ################### #

def grouped(l, n):
    # Yield successive n-sized chunks from l.
    for i in range(0, len(l), n):
        yield l[i:i + n]


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
    return range(1, number + 1)


@register.filter
def get_domain(link):
    """
    Get domain from start link.
    :param link:
    :return domain:
    """
    return urlparse(link).netloc


def _get_thumbnail_path(photo_path, width):
    """Return thumbnail path with dirs created."""
    path_dict = photo_path.split('/')
    path = Path('%s/thumb/' % ('/'.join(path_dict[:-1])))
    if path.is_dir() is False:
        path.mkdir()
    path = Path(('%s/%s/' % (str(path), width)).replace('//', '/'))
    if path.is_dir() is False:
        path.mkdir()
    return '%s/%s' % (str(path), path_dict[-1].split('.')[0] + '.webp')


def thumbnail_from_path(photo_path, width=300, height=None):
    """
       Create thumbnail if not exists for current image.
       Returns: url to thumbnail.
    """
    thumb_path = Path(_get_thumbnail_path(photo_path, width))
    if thumb_path.is_file() is False:
        try:
            im = Image.open(photo_path)
        except FileNotFoundError:
            return
        if height is None:
            height = int((float(im.size[1]) * float(width / float(im.size[0]))))
        im = im.resize((width, height), Image.LANCZOS)
        im.save(thumb_path, format='webp', quality=80)
    return ('%s%s' % (settings.MEDIA_URL, str(thumb_path).replace(settings.MEDIA_ROOT, ""))).replace('//', '/')
