# -*- coding: utf-8 -*-
import hashlib

from django.views.generic import FormView, View
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, HttpResponse, Http404
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string

from appl.pro_auth.forms import UserCreationForm
from appl.pro_auth.models import User


class RegisterView(FormView):
    form_class = UserCreationForm
    template_name = 'pro_auth/register.html'

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.validation_key = hashlib.sha256(
            str('new_user_%s_%s' % (user.email, user.phone1)).encode('utf-8')).hexdigest()
        user.save()
        user.email_user(_("Confirmation of user email."),
                        render_to_string('pro_auth/confirmation_email.html',
                                         {'hash': user.validation_key}),
                        "agr@agromega.in.ua")
        # TODO: need to ajax mixin creation
        return HttpResponse("ok")


class Login(FormView):
    form_class = AuthenticationForm
    template_name = 'pro_auth/login.html'

    def form_valid(self, form):
        login(self.request, form.get_user())
        return HttpResponse('ok')


class Logout(View):
    """Redirects to main page if user logout."""
    url = '/'

    def get(self, request):
        logout(request)
        return HttpResponseRedirect(self.url)


class UserEmailConfirm(View):

    def get(self, request, **kwargs):
        validation_key = kwargs.get('hash', '')
        if validation_key:
            try:
                user = User.objects.get(validation_key=validation_key)
            except User.DoesNotExist:
                raise Http404
            user.is_active = True
            user.validation_key = ''
            user.save()
            login(request, user)
            return HttpResponseRedirect('/')
        raise Http404
