import base64
import hashlib
import hmac
from urllib.parse import urlparse

from django import template
from django.conf import settings
from django.core.files.storage import storages
from django.urls import reverse

from core.adverts.models import Advert
from core.classifier.models import Category
from core.posts.models import Post

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
    context = {"adverts": Advert.active_objects.values("title", "image", "pk", "slug")[:4]}
    for advert in context["adverts"]:
        advert["url"] = reverse("adverts:detail", kwargs={"pk": advert["pk"], "slug": advert["slug"]})
        if advert["image"]:
            advert["image"] = imgproxy_url(storages["default"].url(advert["image"]), 200, 150)
    return context


@register.inclusion_tag("posts/post_adverts_block.html")
def random_adverts():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    context = {"adverts": Advert.active_objects.order_by("?").values("title", "image", "pk", "slug")[:4]}
    for advert in context["adverts"]:
        advert["url"] = reverse("adverts:detail", kwargs={"pk": advert["pk"], "slug": advert["slug"]})
        if advert["image"]:
            advert["image"] = imgproxy_url(storages["default"].url(advert["image"]), 200, 150)
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
def thumbnail(photo_obj, width=300, height=200):
    return imgproxy_url(photo_obj.image.url, width, height) if photo_obj else ""


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
    print(image_url)
    key = bytes.fromhex(settings.IMGPROXY_KEY)
    salt = bytes.fromhex(settings.IMGPROXY_SALT)
    base_url = settings.IMGPROXY_BASE_URL

    encoded_url = base64.urlsafe_b64encode(image_url.encode()).rstrip(b"=").decode()
    path = f"/rs:{resize_type}:{width}:{height}:f:0/{encoded_url}.{output_format}"
    path_b = path.encode()

    signature = hmac.new(key, salt + path_b, hashlib.sha256).digest()

    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    return f"{base_url}/{encoded_signature}{path}"


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
