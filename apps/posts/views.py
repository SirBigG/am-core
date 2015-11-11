from django.shortcuts import render
from django.views.generic import ListView, DetailView

from .models import Post


class ListPostView(ListView):
    model = Post
    # TODO: list_post.html
    template_name = 'list_post.html'


class PostView(DetailView):
    model = Post
    #TODO: post.html
    template_name = 'post.html'

    def get_context_data(self,**kwargs):
        context = super(PostView, self).get_context_data(**kwargs)
        return context

# TODO: url, templates, comments in context for detail