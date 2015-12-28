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


class CommentFormView(SingleObjectMixin, FormView):
    form_class = CommentsForm
    model = Comments

    def form_valid(self, form):
        self.object = form.cleaned_data['post']
        form.save()
        return super(CommentFormView, self).form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class PostDetailView(View):

    def get(self, request, *args, **kwargs):
        view = PostDisplay.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = CommentFormView.as_view()
        return view(request, *args, **kwargs)
