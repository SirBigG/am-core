from django.views.generic import FormView, View, TemplateView, UpdateView
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.urls import reverse


from core.pro_auth.forms import LoginForm, UserChangeForm
from core.posts.models import Post
from core.posts.forms import UpdatePostForm, ProfileAddPostForm


class Login(FormView):
    form_class = LoginForm
    template_name = 'pro_auth/login.html'
    success_url = '/'

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        return super().form_valid(form)


class SocialExistUserLogin(Login):
    def form_valid(self, form):
        self.request.session['user_pk'] = form.get_user().pk
        return HttpResponseRedirect(reverse('social:complete', args=(self.kwargs.get('backend_name'),)))


class Logout(View):
    """Redirects to main page if user logout."""
    url = '/'

    def get(self, request):
        logout(request)
        return HttpResponseRedirect(self.url)


class IsAuthenticate(View):
    """Check current session authentication."""
    def get(self, request):
        if request.is_ajax():
            return JsonResponse({'is_authenticate': 1 if request.user.is_authenticated else 0})
        raise Http404


class ChangeProfileView(FormView):
    form_class = UserChangeForm
    template_name = "pro_auth/profile/change_profile.html"
    success_url = "/profile/change"

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        return form_class(instance=self.request.user, **self.get_form_kwargs())

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class ProfilePostView(TemplateView):
    template_name = "pro_auth/profile/posts.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data()
        context["posts"] = Post.objects.filter(publisher=self.request.user)
        return context


class UpdateProfilePostView(UpdateView):
    form_class = UpdatePostForm
    template_name = "pro_auth/profile/posts_update.html"

    def get_queryset(self):
        return Post.objects.filter(publisher=self.request.user)

    def get_success_url(self):
        return self.get_object().get_absolute_url()

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class CreateProfilePostView(FormView):
    form_class = ProfileAddPostForm
    template_name = "pro_auth/profile/post_create.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(form.instance.get_absolute_url())
