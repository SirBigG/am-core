# -*- coding: utf-8 -*-

from django.views.generic import FormView, TemplateView, \
    View
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect
from django.contrib.auth.forms import AuthenticationForm

from appl.pro_auth.forms import UserCreationForm


class RegisterView(FormView):
    form_class = UserCreationForm
    template_name = 'pro_auth/register.html'

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # todo: add nice redirect with next etc.
        return '/'


class Login(FormView):
    form_class = AuthenticationForm
    template_name = 'pro_auth/login.html'

    def form_valid(self, form):
        login(self.request, form.get_user())
        return HttpResponseRedirect(self.get_success_url())

    def get_success_url(self):
        # todo: add nice redirect with next etc.
        return '/'


class Logout(View):
    """
    Redirect to main page if user logout.
    """
    url = '/'

    def get(self, request):
        logout(request)
        return HttpResponseRedirect(self.url)


class Main(TemplateView):
    # TODO: delete after testing or creatung real main page
    template_name = 'pro_auth/main.html'
