from django.views.generic import ListView, DetailView, TemplateView
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.contrib.postgres.search import SearchVector
from django.http import Http404

from core.posts.models import Post, SearchStatistic
from core.classifier.models import Category


class IndexView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['object_list'] = Post.objects.select_related('country').prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').prefetch_related('tags').filter(status=1)[:10]
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
        context['object_list'] = Post.objects.select_related('country').prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').select_related('rubric__meta').prefetch_related('tags').filter(
            rubric__parent_id=context['category'].pk, status=1)[:4]
        return context


class PostList(ListView):
    """
    View for list of posts by category.
    """
    paginate_by = 20
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

    def get_queryset(self):
        return Post.objects.select_related('country').prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').select_related('rubric__meta').prefetch_related('tags').filter(
            rubric_id=get_object_or_404(Category, slug=self.kwargs['child']).id, status=1)


class PostSearchView(ListView):
    paginate_by = 20
    template_name = 'posts/search.html'

    def get_queryset(self):
        if self.request.GET.get('q', ''):
            SearchStatistic.objects.create(**{"fingerprint": "fingerprint",
                                              "search_phrase": self.request.GET.get('q')})
        return Post.objects.select_related('country').prefetch_related('photo').select_related(
            'rubric').select_related('rubric__parent').prefetch_related('tags').annotate(
            search=SearchVector('text')).filter(search=self.request.GET.get('q', ''))


class PostDetail(DetailView):
    """
    Return one post from list.
    """
    model = Post
    template_name = 'posts/detail.html'


class SiteMap(TemplateView):
    template_name = 'sitemap.xml'

    def get_context_data(self, **kwargs):
        context = super(SiteMap, self).get_context_data(**kwargs)
        context['base'] = settings.HOST + '/'
        context['urls'] = [settings.HOST + p.get_absolute_url() for p in Post.objects.select_related(
            'rubric').prefetch_related('rubric__parent').filter(status=1).exclude(rubric__slug__contains='-user')]
        context['urls'].extend([
            settings.HOST + "/" + slug + "/" for slug in Category.objects.filter(
                level=1).exclude(slug__contains='-user').values_list('slug', flat=True)])
        return context
