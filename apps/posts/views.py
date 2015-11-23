from django.shortcuts import render
from django.views.generic import ListView, DetailView

from .models import Post, Comments


class ListPostView(ListView):
    model = Post
    template_name = 'posts/list_post.html'
    paginate_by = 10


class PostView(DetailView):
    model = Post
    template_name = 'posts/post.html'

    def get_context_data(self,**kwargs):
        context = super(PostView, self).get_context_data(**kwargs)
        context['comments'] = Comments.objects.filter(post=self.object).order_by('-publish_date')
        return context
