import logging
from itertools import groupby
from datetime import date, datetime, timedelta

from dal import autocomplete
from django.views.generic import ListView, DetailView, TemplateView, FormView
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.http import Http404, HttpResponseRedirect, HttpResponseGone
from django.db.models import F

from core.adverts.models import Advert
from core.classifier.models import Category
from core.posts.models import Post, SearchStatistic, Photo
from core.posts.forms import PostForm, PhotoForm


class IndexView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        from core.events.models import Event
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.filter(
            id__in=Post.objects.order_by('-hits').values_list('rubric__parent_id')[:8])
        context['events'] = Event.objects.select_related('location').filter(
            status=1, start__gte=date.today()).order_by('start')[:4]
        context['object_list'] = Post.objects.select_objects().active().order_by('-publish_date')[:8]
        context['random_posts'] = Post.objects.select_objects().active().order_by('?')[:8]
        context['random_adverts'] = Advert.objects.filter(
            updated__gte=datetime.now() - timedelta(days=14)).order_by('?')[:8]
        return context


class ParentRubricView(TemplateView):
    """For base rubric text."""
    template_name = 'posts/parent_index.html'

    def get_context_data(self, **kwargs):
        """
        Get extra context for classifier to view.
        """
        context = super().get_context_data(**kwargs)
        context['category'] = get_object_or_404(Category, slug=self.kwargs['parent'])
        context['object_list'] = Post.objects.select_objects().filter(
            rubric__parent_id=context['category'].pk).active()[:4]
        return context


class PostListView(TemplateView):
    template_name = "posts/list_order.html"

    def get_context_data(self, **kwargs):
        category = Category.objects.select_related('meta').filter(slug=self.kwargs['child']).first()
        if category is None:
            raise Http404
        posts = Post.objects.filter(rubric_id=category.id).values('title', 'absolute_url').active()
        posts = [[key, list(g)] for key, g in groupby(sorted(posts, key=lambda x: x["title"]),
                                                      key=lambda x: x['title'][0])]
        return {"posts": posts,
                "category": category,
                "view": self,
                "request": self.request}


class PostList(ListView):
    """
    View for list of posts by category.
    """
    paginate_by = 50
    template_name = 'posts/list.html'
    ordering = '-publish_date'

    def get_context_data(self, **kwargs):
        """
        Get extra context for classifier to view.
        """
        context = super().get_context_data(**kwargs)
        category = Category.objects.select_related('meta').filter(slug=self.kwargs['child']).first()
        if category is None:
            raise Http404
        context['category'] = category
        return context

    def get_ordering(self):
        if self.request.GET.get("order"):
            return "title"
        return self.ordering

    def get_queryset(self):
        return Post.objects.select_objects().filter(
            rubric_id=get_object_or_404(Category, slug=self.kwargs['child']).id).active().order_by(self.get_ordering())


class PostSearchView(ListView):
    paginate_by = 20
    template_name = 'posts/search.html'

    def get_queryset(self):
        if self.request.GET.get('q', ''):
            SearchStatistic.objects.create(**{"fingerprint": "fingerprint",
                                              "search_phrase": self.request.GET.get('q')})
        return Post.objects.select_objects().active().annotate(
            rank=SearchRank(F('text_search'), SearchQuery(self.request.GET.get('q', ''),
                                                          config='english'))).filter(rank__gt=0.03).order_by('-rank')


class PostDetail(DetailView):
    """
    Return one post from list.
    """
    model = Post
    template_name = 'posts/detail.html'

    def get_context_data(self, **kwargs):
        """
        Get extra context for classifier to view.
        """
        context = super().get_context_data(**kwargs)
        try:
            context['main_photo_object'] = context['object'].photo.first()
        except Exception as e:
            logging.error(e)
            context['main_photo_object'] = None
        context['photo_count'] = context['object'].photo.count()
        context['category'] = context['object'].rubric
        context['publisher_name'] = context['object'].publisher.get_full_name()
        return context


class PostFormView(FormView):
    form_class = PostForm
    template_name = "posts/form.html"

    def form_valid(self, form):
        instance = form.save()
        return HttpResponseRedirect(instance.get_absolute_url())


class SiteMap(TemplateView):
    template_name = 'sitemap.xml'

    def get_context_data(self, **kwargs):
        from core.events.models import Event
        context = super(SiteMap, self).get_context_data(**kwargs)
        context['base'] = settings.HOST + '/'
        context['urls'] = [
            {"loc": f"{settings.HOST}/events/"},
            {"loc": f"{settings.HOST}/news/"},
            {"loc": f"{settings.HOST}/adverts/"},
        ]
        context['urls'].extend([{"loc": f"{settings.HOST}/{slug}/"} for slug in Category.objects.filter(
            level=1, is_active=True).values_list('slug', flat=True)])
        context['urls'].extend([{"loc": f"{settings.HOST}{absolute_url}"} for absolute_url in Category.objects.filter(
            level=2, is_active=True).values_list('absolute_url', flat=True)])
        context['urls'].extend([{"loc": f'{settings.HOST}{p["absolute_url"]}',
                                 "lastmod": p["update_date"]} for p in Post.objects.filter(
            status=True).values('update_date', 'absolute_url')])
        context['urls'].extend([{"loc": f"{settings.HOST}/events/{slug}.html"} for slug in Event.objects.filter(
            status=1).values_list('slug', flat=True)])
        return context


class SitemapIndexView(TemplateView):
    template_name = 'sitemap_index.xml'

    def get_context_data(self, **kwargs):
        context = super(SitemapIndexView, self).get_context_data(**kwargs)
        try:
            advert_lastmod = Advert.active_objects.latest('updated').updated
        except Advert.DoesNotExist:
            advert_lastmod = datetime.now()
        context['urls'] = [
            {
                "loc": f"{settings.HOST}/sitemap-main.xml",
                "lastmod": Post.objects.filter(status=True).latest('update_date').update_date
            },
            {
                "loc": f"{settings.HOST}/sitemap-adverts.xml",
                "lastmod": advert_lastmod
            },
            {
                "loc": f"{settings.HOST}/sitemap-news.xml",
                "lastmod": datetime.now()
            },
        ]
        return context


class GalleryView(ListView):
    paginate_by = 48
    template_name = 'posts/gallery.html'

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['post'] = Post.objects.filter(pk=self.kwargs.get('post_id')).first()
        return context

    def get_queryset(self):
        return Photo.objects.filter(post_id=self.kwargs.get('post_id'))


class AddPhotoView(FormView):
    form_class = PhotoForm
    template_name = 'posts/photo_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["post"] = Post.objects.filter(id=self.kwargs.get('post_id'))
        return context

    def get_initial(self):
        return {'post_id': self.kwargs.get('post_id')}

    def form_valid(self, form):
        instance = form.save()
        return HttpResponseRedirect(instance.post.get_absolute_url())

    def get(self, request, *args, **kwargs):
        context = self.get_context_data()
        if context['post'] is None:
            return HttpResponseGone()
        return super().get(request, *args, **kwargs)


class PostAutocomplete(autocomplete.Select2QuerySetView):
    """
    Return locations queryset.
    """
    def get_queryset(self):
        qs = Post.objects.all()
        if self.q:
            qs = qs.filter(title__icontains=self.q)
        return qs