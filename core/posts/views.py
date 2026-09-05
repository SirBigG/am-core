import logging
import os
from datetime import date, datetime, timedelta
from itertools import groupby
from urllib.parse import urlencode

from dal import autocomplete
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.core.cache import cache
from django.db.models import F
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.views.generic import DetailView, ListView, RedirectView, TemplateView

from core.adverts.models import Advert
from core.classifier.models import Category
from core.companies.market import publication_market_context
from core.posts.category_attribute_filters import apply_category_attribute_filters, build_category_attribute_filters
from core.posts.category_attributes import get_public_category_attribute_groups
from core.posts.models import Photo, Post, SearchStatistic
from core.posts.recommendations import get_random_recommendations
from core.posts.templatetags.post_extras import full_url
from core.registry.models import Variety
from core.utils.rotating import get_rotating_ids, order_by_id_list


def _bounded_positive_ids(value, limit=20):
    ids = []
    for raw_id in (value or "").split(","):
        try:
            post_id = int(raw_id)
        except TypeError, ValueError:
            continue
        if post_id > 0 and post_id not in ids:
            ids.append(post_id)
        if len(ids) == limit:
            break
    return ids


@require_GET
@never_cache
def random_post_recommendations(request):
    current_ids = _bounded_positive_ids(request.GET.get("current"), limit=1)
    current_post_id = current_ids[0] if current_ids else None
    excluded_ids = _bounded_positive_ids(request.GET.get("exclude"))
    posts = get_random_recommendations(
        current_post_id=current_post_id,
        exclude_ids=excluded_ids,
    )
    refresh_params = {"exclude": ",".join(str(post.pk) for post in posts)}
    if current_post_id:
        refresh_params["current"] = current_post_id
    refresh_url = f"{reverse('random-post-recommendations')}?{urlencode(refresh_params)}"
    return render(
        request,
        "posts/random_posts.html",
        {
            "posts": posts,
            "refresh_url": refresh_url,
        },
    )


def service_worker(request):
    """Serve the service worker from the current origin."""
    response = FileResponse(
        open(os.path.join(settings.BASE_DIR, "pwa", "service-worker.js"), "rb"),
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    return response


class IndexView(TemplateView):
    template_name = "index.html"

    def get_context_data(self, **kwargs):
        from core.events.models import Event

        context = super().get_context_data(**kwargs)
        _ids = set(Post.objects.order_by("-hits").values_list("rubric__parent_id", flat=True)[:100])
        context["categories"] = Category.objects.filter(id__in=list(_ids)[:8])
        context["events"] = (
            Event.objects.select_related("location").filter(status=1, start__gte=date.today()).order_by("start")[:4]
        )
        context["object_list"] = Post.objects.select_objects().active().order_by("-publish_date")[:8]
        active_posts = Post.objects.active()
        random_post_ids = get_rotating_ids(active_posts, "homepage", 8)
        context["random_posts"] = order_by_id_list(Post.objects.select_objects(), random_post_ids)
        context["random_adverts"] = []
        if settings.ENABLE_INTERNAL_ADVERTS:
            recent_adverts = Advert.objects.filter(updated__gte=datetime.now() - timedelta(days=14)).prefetch_related(
                "photos"
            )
            random_advert_ids = get_rotating_ids(recent_adverts, "homepage", 8)
            context["random_adverts"] = order_by_id_list(recent_adverts, random_advert_ids)
        return context


class PlantDiaryLandingView(TemplateView):
    template_name = "plant_diary.html"


class ParentRubricView(TemplateView):
    """For base rubric text."""

    template_name = "posts/parent_index.html"

    def get_context_data(self, **kwargs):
        """Get extra context for classifier to view."""
        context = super().get_context_data(**kwargs)
        context["category"] = get_object_or_404(Category, slug=self.kwargs["parent"])
        context["object_list"] = (
            Post.objects.select_objects().filter(rubric__parent_id=context["category"].pk).active()[:4]
        )
        return context


class PostListView(TemplateView):
    template_name = "posts/list_order.html"

    def _get_post_countries(self, rubric_id):
        cache_key = f"post_countries_{rubric_id}"
        countries = cache.get(cache_key)
        if not countries:
            countries = (
                Post.objects.filter(country__isnull=False, rubric_id=rubric_id)
                .values_list("country__slug", "country__value")
                .distinct()
            )
            countries = dict(countries)
            cache.set(cache_key, countries, 3600)
        return countries

    def _filter_posts(self, posts):
        if self.request.GET.get("country"):
            posts = posts.filter(country__slug=self.request.GET.get("country"))
        return posts

    def get_context_data(self, **kwargs):
        category = Category.objects.select_related("meta").filter(slug=self.kwargs["child"]).first()
        if category is None:
            raise Http404
        posts_queryset = Post.objects.filter(rubric_id=category.id).active()
        posts_queryset = self._filter_posts(posts_queryset)
        attribute_filters = build_category_attribute_filters(category, posts_queryset, self.request.GET)
        posts_queryset = apply_category_attribute_filters(posts_queryset, category, self.request.GET)
        posts = list(posts_queryset.values("title", "absolute_url", "country__short_slug"))
        post_count = len(posts)
        posts = [
            [key, list(g)] for key, g in groupby(sorted(posts, key=lambda x: x["title"]), key=lambda x: x["title"][0])
        ]
        return {
            "posts": posts,
            "category": category,
            "view": self,
            "request": self.request,
            "countries": self._get_post_countries(category.id),
            "attribute_filters": attribute_filters,
            "has_active_filters": bool(self.request.GET),
            "post_count": post_count,
            "group_count": len(posts),
        }


class PostList(ListView):
    """View for list of posts by category."""

    paginate_by = 50
    template_name = "posts/list.html"
    ordering = "-publish_date"

    def get_context_data(self, **kwargs):
        """Get extra context for classifier to view."""
        context = super().get_context_data(**kwargs)
        category = Category.objects.select_related("meta").filter(slug=self.kwargs["child"]).first()
        if category is None:
            raise Http404
        context["category"] = category
        return context

    def get_ordering(self):
        if self.request.GET.get("order"):
            return "title"
        return self.ordering

    def get_queryset(self):
        return (
            Post.objects.select_objects()
            .filter(rubric_id=get_object_or_404(Category, slug=self.kwargs["child"]).id)
            .active()
            .order_by(self.get_ordering())
        )


class PostSearchView(ListView):
    paginate_by = 20
    template_name = "posts/search.html"

    def get_queryset(self):
        if self.request.GET.get("q", ""):
            SearchStatistic.objects.create(**{"fingerprint": "fingerprint", "search_phrase": self.request.GET.get("q")})
        return (
            Post.objects.select_objects()
            .active()
            .annotate(rank=SearchRank(F("text_search"), SearchQuery(self.request.GET.get("q", ""), config="english")))
            .filter(rank__gt=0.01)
            .order_by("-rank")
        )


class PostDetail(DetailView):
    """Return one post from list."""

    model = Post
    template_name = "posts/detail.html"

    def get_queryset(self):
        return Post.objects.select_objects().select_related("publisher", "meta")

    def get_context_data(self, **kwargs):
        """Get extra context for classifier to view."""
        context = super().get_context_data(**kwargs)
        try:
            context["main_photo_object"] = context["object"].primary_photo
            if context["main_photo_object"]:
                context["main_photo_thumbnail"] = context["main_photo_object"].image.url
                context["main_photo_full_url"] = full_url(context["main_photo_thumbnail"])
        except Exception as e:
            logging.error(e)
            context["main_photo_object"] = None
        context["photo_count"] = context["object"].public_photo_count
        context["category"] = context["object"].rubric
        context["publisher_name"] = context["object"].publisher.get_full_name()
        context["registry_variety_exists"] = Variety.objects.filter(publication_id=context["object"].id).exists()
        context["publication_market"] = publication_market_context(
            context["object"], context["registry_variety_exists"]
        )
        context["category_attribute_groups"] = get_public_category_attribute_groups(context["object"])
        return context


class PostFormView(RedirectView):
    permanent = True
    url = "/create/"


class SiteMap(TemplateView):
    template_name = "sitemap.xml"

    def get_context_data(self, **kwargs):
        from core.events.models import Event

        context = super().get_context_data(**kwargs)
        base_url = settings.HOST.rstrip("/")
        urls = [
            {"loc": f"{base_url}/"},
            {"loc": f"{base_url}/events/"},
            {"loc": f"{base_url}/news/"},
            {"loc": f"{base_url}/adverts/"},
        ]
        urls.extend(
            [
                {"loc": f"{base_url}/{slug}/"}
                for slug in Category.objects.filter(level=1, is_active=True).values_list("slug", flat=True)
            ]
        )
        urls.extend(
            [
                {"loc": f"{base_url}{absolute_url}"}
                for absolute_url in Category.objects.filter(level=2, is_active=True).values_list(
                    "absolute_url", flat=True
                )
            ]
        )
        urls.extend(
            [
                {"loc": f'{base_url}{p["absolute_url"]}', "lastmod": p["update_date"]}
                for p in Post.objects.filter(status=True).values("update_date", "absolute_url")
            ]
        )
        urls.extend(
            [
                {"loc": f"{base_url}/events/{slug}.html"}
                for slug in Event.objects.filter(status=1).values_list("slug", flat=True)
            ]
        )
        context["urls"] = list({url["loc"]: url for url in urls}.values())
        return context


class SitemapIndexView(TemplateView):
    template_name = "sitemap_index.xml"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_url = settings.HOST.rstrip("/")
        latest_post = Post.objects.filter(status=True).order_by("-update_date").first()
        latest_advert = Advert.active_objects.order_by("-updated").first()
        context["urls"] = [
            {
                "loc": f"{base_url}/sitemap-main.xml",
                "lastmod": latest_post.update_date if latest_post else None,
            },
            {
                "loc": f"{base_url}/sitemap-adverts.xml",
                "lastmod": latest_advert.updated if latest_advert else None,
            },
            {"loc": f"{base_url}/sitemap-news.xml"},
            {"loc": f"{base_url}/agromarket/sitemap.xml"},
            {"loc": f"{settings.FORUM_BASE_URL.rstrip('/')}/sitemap.xml"},
        ]
        return context


class GalleryView(ListView):
    paginate_by = 48
    template_name = "posts/gallery.html"

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context["post"] = Post.objects.filter(pk=self.kwargs.get("post_id")).first()
        return context

    def get_queryset(self):
        return Photo.objects.filter(post_id=self.kwargs.get("post_id"))


class PostAutocomplete(autocomplete.Select2QuerySetView):
    """Return locations queryset."""

    def get_queryset(self):
        qs = Post.objects.prefetch_related("rubric").all()
        if self.q:
            qs = qs.filter(title__icontains=self.q)
        return qs
