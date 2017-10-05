from __future__ import unicode_literals

from django.views.generic import ListView, DetailView, TemplateView
from django.conf import settings
from django.shortcuts import get_object_or_404

from core.posts.models import Post
from core.classifier.models import Category


class ParentRubricView(TemplateView):
    """For base rubric text."""
    template_name = 'posts/parent_index.html'

    def get_context_data(self, **kwargs):
        """
        Get extra context for classifier to view.
        """
        context = super(ParentRubricView, self).get_context_data(**kwargs)
        context['category'] = get_object_or_404(Category, slug=self.kwargs['parent'])
        context['object_list'] = Post.objects.filter(rubric__parent_id=context['category'].pk)[:4]
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
        context = super(PostList, self).get_context_data(**kwargs)
        context['category'] = get_object_or_404(Category, slug=self.kwargs['child'])
        return context

    def get_queryset(self):
        return Post.objects.filter(rubric_id=get_object_or_404(Category, slug=self.kwargs['child']).id, status=1)


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
        context['urls'] = [settings.HOST + p.get_absolute_url() for p in Post.objects.filter(status=1)]
        return context
