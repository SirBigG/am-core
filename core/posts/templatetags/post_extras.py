from urllib.parse import urlparse

from django import template
from django.conf import settings
from django.core.files.storage import storages

from core.adverts.models import Advert
from core.classifier.models import Category
from core.posts.models import Post
from core.utils.images import imgproxy_url as build_image_url

register = template.Library()


@register.inclusion_tag("posts/main_menu.html")
def main_menu():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    return {"roots": Category.objects.filter(level=0, is_active=True).order_by("value")}


@register.inclusion_tag("posts/second_menu.html")
def second_menu(parent_slug, current_slug=None):
    return {
        "menu_items": Category.objects.get(slug=parent_slug).get_children().values("slug", "value", "absolute_url"),
        "slug": current_slug,
    }


@register.inclusion_tag("posts/breadcrumbs.html")
def breadcrumbs(category, post_title=None):
    """Breadcrumbs block."""
    return {
        "items": category.get_ancestors(include_self=True).values("value", "absolute_url")[1:],
        "post_title": post_title,
    }


@register.inclusion_tag("posts/post_adverts_block.html")
def post_adverts():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    context = {"adverts": []}
    if not settings.ENABLE_INTERNAL_ADVERTS:
        return context
    for advert in Advert.active_objects.prefetch_related("photos")[:4]:
        image = imgproxy_url(advert.primary_image_url, 200, 150) if advert.primary_image_url else ""
        context["adverts"].append({"title": advert.title, "image": image, "url": advert.get_absolute_url()})
    return context


@register.inclusion_tag("posts/post_adverts_block.html")
def random_adverts():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    context = {"adverts": []}
    if not settings.ENABLE_INTERNAL_ADVERTS:
        return context
    for advert in Advert.active_objects.prefetch_related("photos").order_by("?")[:4]:
        image = imgproxy_url(advert.primary_image_url, 200, 150) if advert.primary_image_url else ""
        context["adverts"].append({"title": advert.title, "image": image, "url": advert.get_absolute_url()})
    return context


@register.inclusion_tag("posts/relative_posts.html")
def relative_posts(category_id):
    context = {
        "posts": Post.objects.filter(rubric_id=category_id, status=True)
        .values("id", "title", "absolute_url", "photo__image")
        .order_by("?")[:4]
    }
    for post in context["posts"]:
        if post["photo__image"]:
            post["photo__image"] = imgproxy_url(storages["default"].url(post["photo__image"]), 200, 150)
    return context


@register.inclusion_tag("posts/random_posts.html")
def random_posts():
    context = {
        "posts": Post.objects.filter(status=True)
        .values("id", "title", "absolute_url", "photo__image")
        .order_by("?")[:4]
    }
    for post in context["posts"]:
        if post["photo__image"]:
            post["photo__image"] = imgproxy_url(storages["default"].url(post["photo__image"]), 200, 150)
    return context


@register.simple_tag
def full_url(url):
    """Create full url with hostname.

    :param: absolute url
    :return: full url
    """
    return settings.HOST + url


@register.simple_tag
def thumbnail(photo_obj, width=300, height=200, object_attr="image"):
    return imgproxy_url(getattr(photo_obj, object_attr).url, width, height) if photo_obj else ""


@register.simple_tag
def imgproxy_url(image_url, width, height, resize_type="fit", output_format="webp"):
    """Generate Imgproxy URL for the given image.

    :param image_url: URL of the original image
    :param width: Desired width of the thumbnail
    :param height: Desired height of the thumbnail
    :param resize_type: Resize type (default is 'fit')
    :param output_format: Output format (default is 'webp')
    :return: Imgproxy URL
    """
    return build_image_url(image_url, width, height, resize_type=resize_type, output_format=output_format)


# ####################    Filters    ################### #


def grouped(value, n):
    # Yield successive n-sized chunks from l.
    for i in range(0, len(value), n):
        yield value[i : i + n]


@register.filter
def group_by(value, arg):
    """For grouping iterable items in groups by arg size.

    :param value: iterable,
    :param arg: int :return iterator
    """
    return grouped(value, arg)


@register.filter
def divide_into_cols(value, arg):
    """For grouping iterable items in groups by arg size.

    :param value: iterable,
    :param arg: int :return iterator
    """
    per_col = len(value) // arg + 1
    return [value[i : i + per_col] for i in range(0, len(value), per_col)]


@register.filter
def times(number):
    """For using range function in templatetags.

    :param number: int
    :return range obj:
    """
    return range(1, number + 1)


@register.filter
def get_domain(link):
    """Get domain from start link.

    :param link:
    :return domain:
    """
    return urlparse(link).netloc
