from django.views.generic import FormView, View, TemplateView, UpdateView, ListView, DetailView
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.urls import reverse

from core.pro_auth.forms import LoginForm, UserChangeForm
from core.posts.models import Post
from core.posts.forms import UpdatePostForm, ProfileAddPostForm
from core.diary.forms import DiaryForm, DiaryItemForm
from core.diary.models import Diary
from core.adverts.forms import AdvertForm
from core.adverts.models import Advert


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
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
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


class ProfilePostView(ListView):
    paginate_by = 25
    ordering = "-updated"
    template_name = "pro_auth/profile/posts.html"

    def get_queryset(self):
        return Post.objects.filter(publisher=self.request.user)


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


class AddDiaryView(FormView):
    form_class = DiaryForm
    template_name = "pro_auth/profile/add_diary.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(form.instance.get_profile_absolute_url())


class ProfileDiaryListView(ListView):
    template_name = "pro_auth/profile/diary_list.html"
    model = Diary

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user)


class ProfileDiaryDetailView(DetailView):
    model = Diary
    template_name = "pro_auth/profile/diary_detail.html"

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user)


class UpdateProfileDiaryView(UpdateView):
    form_class = DiaryForm
    template_name = "pro_auth/profile/diary_update.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user)

    def get_success_url(self):
        return self.get_object().get_profile_absolute_url()

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)


class AddDiaryItemView(FormView):
    form_class = DiaryItemForm
    template_name = "pro_auth/profile/add_diary_item.html"

    def get_context_data(self, **kwargs):
        context = super(AddDiaryItemView, self).get_context_data(**kwargs)
        context["diary"] = Diary.objects.get(pk=self.kwargs["diary_id"])
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["diary"] = Diary.objects.get(pk=self.kwargs["diary_id"])
        return kwargs

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse('pro_auth:profile-diary-detail', kwargs={"pk": self.kwargs["diary_id"]}))


class ProfileAdvertListView(ListView):
    template_name = "pro_auth/profile/advert_list.html"
    model = Advert
    ordering = "-updated"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user)


class ProfileAdvertAddView(FormView):
    form_class = AdvertForm
    template_name = "pro_auth/profile/advert_add.html"

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse('pro_auth:profile-adverts'))


class UpdateProfileAdvertsView(UpdateView):
    form_class = AdvertForm
    template_name = "pro_auth/profile/advert_update.html"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user)

    def get_success_url(self):
        return reverse('pro_auth:profile-adverts')

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
