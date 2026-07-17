import json
from urllib.parse import urlencode, urlparse

from django import template
from django.conf import settings
from django.core.cache import cache
from django.core.files.storage import storages
from django.urls import reverse
from django.utils.html import strip_tags
from django.utils.safestring import mark_safe

from core.adverts.models import Advert
from core.classifier.models import Category
from core.posts.models import Post
from core.utils.images import imgproxy_url as build_image_url
from core.utils.rotating import get_rotating_ids, order_by_id_list, rotation_bucket

register = template.Library()


def _json_ld(data):
    return mark_safe(json.dumps(data, ensure_ascii=False, separators=(",", ":")))


def _category_ancestors(category):
    ancestors = getattr(category, "_public_ancestors", None)
    if ancestors is None:
        ancestors = list(category.get_ancestors(include_self=True))
        category._public_ancestors = ancestors
    return ancestors


@register.simple_tag
def default_og_image():
    return public_url(settings.STATIC_URL + "posts/og-default.png")


@register.simple_tag
def site_structured_data():
    origin = settings.HOST.rstrip("/")
    return _json_ld(
        {
            "@context": "https://schema.org",
            "@graph": [
                {
                    "@type": "Organization",
                    "@id": f"{origin}/#organization",
                    "name": "AgroMega",
                    "url": f"{origin}/",
                    "logo": public_url(settings.STATIC_URL + "posts/logo.png"),
                },
                {
                    "@type": "WebSite",
                    "@id": f"{origin}/#website",
                    "url": f"{origin}/",
                    "name": "AgroMega",
                    "publisher": {"@id": f"{origin}/#organization"},
                    "potentialAction": {
                        "@type": "SearchAction",
                        "target": {"@type": "EntryPoint", "urlTemplate": f"{origin}/search/?q={{search_term_string}}"},
                        "query-input": "required name=search_term_string",
                    },
                },
            ],
        }
    )


@register.simple_tag
def breadcrumb_structured_data(category, current_title=None):
    entries = [{"name": "Головна", "item": public_url("/")}]
    for ancestor in _category_ancestors(category)[1:]:
        entries.append(
            {"name": ancestor.value, "item": public_url(ancestor.absolute_url or ancestor.get_absolute_url())}
        )
    if current_title:
        entries.append({"name": current_title, "item": None})
    items = []
    for position, entry in enumerate(entries, 1):
        item = {"@type": "ListItem", "position": position, "name": entry["name"]}
        if entry["item"]:
            item["item"] = entry["item"]
        items.append(item)
    return _json_ld({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items})


@register.simple_tag(takes_context=True)
def collection_structured_data(context, title, objects):
    elements = []
    for position, obj in enumerate(objects, 1):
        if isinstance(obj, dict):
            name = obj.get("title") or obj.get("data", {}).get("title")
            url = obj.get("absolute_url") or obj.get("url") or obj.get("data", {}).get("link")
        else:
            name = getattr(obj, "title", None) or getattr(obj, "value", None)
            url = getattr(obj, "absolute_url", None)
            if not url and hasattr(obj, "get_absolute_url"):
                url = obj.get_absolute_url()
        if name and url:
            elements.append({"@type": "ListItem", "position": position, "name": str(name), "url": public_url(url)})
    return _json_ld(
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "name": title,
            "url": public_url(context["request"].path),
            "mainEntity": {"@type": "ItemList", "numberOfItems": len(elements), "itemListElement": elements},
        }
    )


@register.simple_tag
def article_structured_data(post, category, image_url="", author_name=""):
    description = strip_tags(getattr(post, "meta_description", "") or str(post.text))
    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post.meta.title if post.meta else f"{post.title} | {category.value}",
        "description": description,
        "datePublished": post.publish_date.isoformat(),
        "dateModified": post.update_date.isoformat(),
        "mainEntityOfPage": public_url(post.get_absolute_url()),
        "author": {"@type": "Person", "name": str(post.author or author_name)},
        "publisher": {"@id": f"{settings.HOST.rstrip('/')}/#organization"},
    }
    if image_url:
        data["image"] = [image_url]
    return _json_ld(data)


@register.simple_tag
def news_structured_data(obj):
    data = {
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": obj.get("title", ""),
        "description": strip_tags(obj.get("description", "")),
        "url": obj.get("url", ""),
        "publisher": {"@id": f"{settings.HOST.rstrip('/')}/#organization"},
    }
    if obj.get("image"):
        data["image"] = [obj["image"]]
    if obj.get("created"):
        data["datePublished"] = obj["created"]
    return _json_ld(data)


@register.simple_tag
def event_structured_data(event):
    data = {
        "@context": "https://schema.org",
        "@type": "Event",
        "name": event.title,
        "description": strip_tags(str(event.text)),
        "startDate": event.start.isoformat(),
        "endDate": event.stop.isoformat(),
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "url": public_url(event.get_absolute_url()),
        "location": {
            "@type": "Place",
            "name": str(event.location),
            "address": event.address,
        },
        "organizer": {"@id": f"{settings.HOST.rstrip('/')}/#organization"},
    }
    if event.poster:
        data["image"] = [public_url(event.poster.url)]
    return _json_ld(data)


@register.simple_tag
def canonical_url(request):
    """Return the canonical public URL for the current path without its query
    string."""
    return public_url(request.path or "/")


def public_url(path):
    """Build an absolute URL on the configured public origin."""
    if str(path).startswith(("http://", "https://")):
        return str(path)
    return f"{settings.HOST.rstrip('/')}/{path.lstrip('/')}"


@register.simple_tag
def robots_content(request):
    """Keep private workflows, search, and query variants out of the index."""
    non_indexable_prefixes = (
        "/adverts/create/",
        "/confirm/",
        "/feedback/",
        "/login/",
        "/logout/",
        "/profile/",
        "/register/",
        "/search/",
        "/service/feedback/",
        "/user/",
    )
    if request.path.startswith(non_indexable_prefixes) or request.GET:
        return "noindex,follow"
    return "index,follow"


@register.inclusion_tag("posts/main_menu.html")
def main_menu():
    """Creating main page menu.

    :return: rubric roots queryset
    """
    return {"roots": Category.objects.filter(level=0, is_active=True).order_by("value")}


@register.inclusion_tag("posts/second_menu.html")
def second_menu(parent_slug, current_slug=None):
    return {
        "menu_items": Category.objects.filter(parent__slug=parent_slug).values("slug", "value", "absolute_url"),
        "slug": current_slug,
    }


@register.inclusion_tag("posts/breadcrumbs.html")
def breadcrumbs(category, post_title=None):
    """Breadcrumbs block."""
    return {
        "items": [
            {"value": ancestor.value, "absolute_url": ancestor.absolute_url}
            for ancestor in _category_ancestors(category)[1:]
        ],
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
def relative_posts(category_id, current_post_id=None):
    posts = _rotating_post_cards(
        Post.objects.filter(rubric_id=category_id, status=True),
        f"relative:{category_id}",
        5,
    )
    return {"posts": [post for post in posts if post["id"] != current_post_id][:4]}


@register.inclusion_tag("posts/random_posts_loader.html")
def random_posts(current_post_id=None):
    params = {"current": current_post_id} if current_post_id else {}
    url = reverse("random-post-recommendations")
    if params:
        url = f"{url}?{urlencode(params)}"
    return {"recommendations_url": url}


def _rotating_post_cards(queryset, scope, limit):
    ids = get_rotating_ids(queryset, scope, limit)
    cache_key = f"public_post_cards_v2:{scope}:{limit}:{rotation_bucket()}:{','.join(map(str, ids))}"
    cards = cache.get(cache_key)
    if cards is None:
        posts = order_by_id_list(Post.objects.select_objects(), ids)
        cards = [
            {
                "id": post.id,
                "title": post.title,
                "absolute_url": post.absolute_url,
                "photo__image": post.primary_photo.image.name if post.primary_photo else "",
            }
            for post in posts
        ]
        cache.set(cache_key, cards, 3660)

    rendered_cards = []
    for card in cards:
        rendered_card = dict(card)
        if rendered_card["photo__image"]:
            rendered_card["photo__image"] = imgproxy_url(
                storages["default"].url(rendered_card["photo__image"]),
                200,
                150,
            )
        rendered_cards.append(rendered_card)
    return rendered_cards


@register.simple_tag
def full_url(url):
    """Create full url with hostname.

    :param: absolute url
    :return: full url
    """
    return public_url(url)


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
