# -*- coding: utf-8 -*-

from django.views.generic import ListView, DetailView, TemplateView
from django.conf import settings
from django.http import Http404

from appl.posts.models import Post
from appl.classifier.models import Category
from appl.posts.serializers import ShortPostSerializer

from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination


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
        context['menu_items'] = Category.objects.get(slug=self.kwargs['parent']).get_children()
        return context

    def get_queryset(self):
        try:
            r = Category.objects.get(slug=self.kwargs['parent']).get_children()
            queryset = Post.objects.filter(rubric_id__in=r)
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
        context['urls'] = [settings.HOST + p.get_absolute_url() for p in Post.objects.all()]
        return context


# #################### API views ##################### #

class SmallPagesPagination(PageNumberPagination):
    page_size = 10


class ApiPostList(ListAPIView):
    queryset = Post.objects.all().order_by('-id')
    serializer_class = ShortPostSerializer
    pagination_class = SmallPagesPagination


class RandomListPaginator(PageNumberPagination):
    page_size = 4


class RandomApiPostList(ListAPIView):
    """Returned five random post objects."""
    queryset = Post.objects.all().order_by('?')
    serializer_class = ShortPostSerializer
    pagination_class = RandomListPaginator
