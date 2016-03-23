# -*- coding: utf-8 -*-

from django.views.generic import ListView, DetailView

from appl.posts.models import Post
from appl.classifier.models import Category


class PostList(ListView):
    paginate_by = 20
    # TODO: create posts/list.html
    # TODO: create second menu
    # TODO: test pagination
    template_name = 'posts/list.html'
    ordering = '-publish_date'

    def get_queryset(self):
        queryset = None
        if 'child' in self.kwargs:
            r = Category.objects.get(slug=self.kwargs['child'])
            queryset = Post.objects.filter(rubric_id=r.id)
        elif 'parent' in self.kwargs:
            r = Category.objects.get(slug=self.kwargs['parent']).get_children()
            queryset = Post.objects.filter(rubric_id__in=r)
        return queryset


# TODO: need tests
class PostDetail(DetailView):
    model = Post
    template_name = 'posts/detail.html'
