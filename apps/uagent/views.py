from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.csrf import csrf_protect
from django.shortcuts import redirect
from django.views.generic import FormView, RedirectView

from forms import UserRegistrationForm


# View for user registration form
class RegistrationFormView(FormView):
    template_name = 'uagent/register.html'
    form_class = UserRegistrationForm
    success_url = '/'

    def form_valid(self, form):
        form.save()
        login(self.request, form.get_user())
        return super(RegistrationFormView,self).form_valid(form)

class LoginFormView(FormView):
    template_name = 'uagent/login.html'
    form_class = AuthenticationForm
    success_url = '/'

    def form_valid(self, form):
        login(self.request, form.get_user())
        return super(LoginFormView,self).form_valid(form)


class LogoutView(RedirectView):
    url = '/'

    def get(self, request, *args, **kwargs):
        logout(request)
        return super(LogoutView, self).get(request, *args, **kwargs)

