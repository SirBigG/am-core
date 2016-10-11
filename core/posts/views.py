from __future__ import unicode_literals

from django.views.generic import ListView, DetailView, TemplateView
from django.conf import settings
from django.http import Http404

from core.posts.models import Post
from core.classifier.models import Category


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
        parent = Category.objects.get(slug=self.kwargs['parent'])
        context['menu_items'] = parent.get_children()
        category = Category.objects.get(slug=self.kwargs['child']) if 'child' in self.kwargs else parent
        context['category'] = category
        return context

    def get_queryset(self):
        try:
            r = Category.objects.get(slug=self.kwargs['parent']).get_children()
            queryset = Post.objects.filter(rubric_id__in=r, status=1)
        except Category.DoesNotExist:
            raise Http404
        if 'child' in self.kwargs:
            try:
                r = Category.objects.get(slug=self.kwargs['child'])
                queryset = queryset.filter(rubric_id=r.id)
            except Category.DoesNotExist:
                raise Http404
        return queryset


class PostDetail(DetailView):
    """
    Return one post from list.
    """
    model = Post
    template_name = 'posts/detail.html'

    def get_context_data(self, **kwargs):
        context = super(PostDetail, self).get_context_data(**kwargs)
        context['menu_items'] = Category.objects.get(slug=self.kwargs['parent']).get_children()
        return context


class SiteMap(TemplateView):
    template_name = 'sitemap.xml'

    def get_context_data(self, **kwargs):
        context = super(SiteMap, self).get_context_data(**kwargs)
        context['base'] = settings.HOST + '/'
        context['urls'] = [settings.HOST + p.get_absolute_url() for p in Post.objects.filter(status=1)]
        return context
