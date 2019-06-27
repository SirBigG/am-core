from django.views.generic import FormView, View
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, Http404, JsonResponse
from django.urls import reverse


from core.pro_auth.forms import LoginForm


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
