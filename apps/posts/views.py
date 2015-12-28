from django.views.generic import ListView, DetailView, FormView, View
from django.views.generic.detail import SingleObjectMixin

from .models import Post
from apps.comment.models import Comments
from apps.comment.forms import CommentsForm


class ListPostView(ListView):
    model = Post
    template_name = 'posts/list_post.html'
    paginate_by = 10


class PostDisplay(DetailView):
    model = Post
    template_name = 'posts/post.html'

    def get_context_data(self,**kwargs):
        context = super(PostDisplay, self).get_context_data(**kwargs)
        context['comments'] = Comments.objects.filter(post=self.object).order_by('-publish_date')
        context['comments_form'] = CommentsForm
        return context
