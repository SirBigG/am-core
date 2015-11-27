from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView, FormView, View
from django.views.generic.detail import SingleObjectMixin
from django.http import HttpResponseForbidden

from .models import Post, Comments
from .forms import CommentsForm


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
    # TODO: create template for form
    template_name = 'posts/post.html'

    def post(self, request, *args, **kwargs):
        if not request.user.is_authenticated():
            return HttpResponseForbidden()
        self.object = self.get_object()
        form = self.form_class(request.POST)
        if form.is_valid():
            form.save()
        return super(CommentFormView, self).post(request, *args, **kwargs)
    # FIXME: Dont work success url. Do it for POST.
    def get_success_url(self):
        return self.object.post.get_absolute_url()


class PostDetailView(View):

    def get(self, request, *args, **kwargs):
        view = PostDisplay.as_view()
        return view(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        view = CommentFormView.as_view()
        return view(request, *args, **kwargs)
