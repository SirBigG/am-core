from __future__ import unicode_literals

import hashlib

from datetime import datetime

from django.views.generic import FormView, View
from django.contrib.auth import login, logout
from django.http import HttpResponseRedirect, HttpResponse, Http404, JsonResponse
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.utils.translation import ugettext_lazy as _
from django.template.loader import render_to_string


from appl.pro_auth.forms import UserCreationForm, EmailConfirmForm
from appl.pro_auth.models import User
from appl.pro_auth.serializers import UserSerializer
from appl.pro_auth.permissions import PersonalPermission

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated


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
        user = form.get_user()
        login(self.request, user)
        data = {'status': 'ok', 'user': user.pk}
        return JsonResponse(data=data)


class Logout(View):
    """Redirects to main page if user logout."""
    url = '/'

    def get(self, request):
        logout(request)
        return HttpResponseRedirect(self.url)


class UserEmailConfirm(View):

    def get(self, request, **kwargs):
        _validation_key = kwargs.get('hash', '')
        if _validation_key:
            try:
                user = User.objects.get(validation_key=_validation_key)
            except User.DoesNotExist:
                raise Http404
            user.is_active = True
            user.validation_key = ''
            user.save()
            login(request, user)
            return HttpResponseRedirect('/')
        raise Http404


class UserPasswordReset(FormView):

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
                          render_to_string('pro_auth/check_password_email.html',
                                           {'hash': _validation_key}),
                          "agr@agromega.in.ua")
            return JsonResponse({'status': 'ok'})

        if isinstance(form, SetPasswordForm):
            _user = form.save(commit=False)
            _user.validation_key = ''
            _user.save()
            login(self.request, _user)
            return HttpResponseRedirect('/')


# TODO: authentication required need
# TODO: get method for update form creation
# TODO: create tokenize authenticate or other for all api login required connections
class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, PersonalPermission]
