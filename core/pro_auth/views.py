from __future__ import unicode_literals

import hashlib

from datetime import datetime

from django.views.generic import FormView, View
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, HttpResponse, Http404, JsonResponse
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string
from django.urls import reverse, reverse_lazy


from core.pro_auth.forms import UserCreationForm, EmailConfirmForm
from core.pro_auth.models import User


class RegisterView(FormView):
    form_class = UserCreationForm
    template_name = 'pro_auth/register.html'
    success_url = reverse_lazy('index')

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        user.validation_key = hashlib.sha256(
            str('new_user_%s_%s' % (user.email, user.phone1)).encode('utf-8')).hexdigest()
        user.save()
        user.email_user(_("Confirmation of user email."),
                        _("Register information"),
                        "agr@agromega.in.ua",
                        html_message=render_to_string('pro_auth/confirmation_email.html',
                                                      {'hash': user.validation_key})
                        )
        return super().form_valid(form)


class SocialRegisterView(RegisterView):
    def form_valid(self, form):
        self.request.session['phone1'] = form.cleanrd_data['phone1']
        return HttpResponseRedirect(reverse('social:complete', args=('vk-oauth2',)))


class Login(FormView):
    form_class = AuthenticationForm
    template_name = 'pro_auth/login.html'
    ajax_template_name = 'pro_auth/login_form.html'
    success_url = '/'

    def form_valid(self, form):
        user = form.get_user()
        login(self.request, user)
        if self.request.is_ajax():
            data = {'status': 'ok', 'user': user.pk}
            return JsonResponse(data=data)
        else:
            return super().form_valid(form)

    def get_template_names(self):
        return [self.ajax_template_name] if self.request.is_ajax() else [self.template_name]


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


class UserEmailConfirm(View):

    def get(self, request, **kwargs):
        _key = kwargs.get('hash', '')
        if _key:
            try:
                user = User.objects.get(validation_key=_key)
            except User.DoesNotExist:
                raise Http404
            user.is_active = True
            user.validation_key = ''
            user.save()
            login(request, user)
            return HttpResponseRedirect('/')
        raise Http404


class UserPasswordReset(FormView):
    """User changing password logic.
       Sends email with hash in email if user exists.
       Checking if hash right and reset password."""
    def get_template_names(self):
        if self.kwargs.get('action') == 'confirm':
            return ['pro_auth/email_confirm_for_pass.html']
        elif self.kwargs.get('action') == 'check':
            return ['pro_auth/check_password.html']

    def get_form_class(self):
        if self.kwargs.get('action') == 'confirm':
            return EmailConfirmForm
        elif self.kwargs.get('action') == 'check' and self.kwargs.get('hash', ''):
            return SetPasswordForm

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()
        if form_class == SetPasswordForm and self.kwargs.get('hash', ''):
            try:
                _user = User.objects.get(validation_key=self.kwargs.get('hash'))
            except User.DoesNotExist:
                raise Http404
            return SetPasswordForm(user=_user, **self.get_form_kwargs())
        return form_class(**self.get_form_kwargs())

    def form_valid(self, form):
        if isinstance(form, EmailConfirmForm):
            _u = form.get_user()
            _validation_key = hashlib.sha256(
                str('pass_reset:%s:%s' % (_u.email, datetime.now())).encode('utf-8')).hexdigest()
            _u.validation_key = _validation_key
            _u.save()
            _u.email_user(_("Confirmation of user email."),
                          _("Changing password email"),
                          "agr@agromega.in.ua",
                          html_message=render_to_string('pro_auth/check_password_email.html',
                                                        {'hash': _validation_key}))
            return JsonResponse({'status': 'ok'})

        if isinstance(form, SetPasswordForm):
            _user = form.save(commit=False)
            _user.validation_key = ''
            _user.save()
            login(self.request, _user)
            return HttpResponseRedirect('/')
