# -*- coding: utf-8 -*-

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate
from django.utils.translation import ugettext_lazy as _



class UserRegistrationForm(forms.ModelForm):
    """
    A form that creates a user, with no privileges, from the given username,
    email and password.
    """

    email = forms.EmailField(label=_("E-mail"),required=True,widget=forms.EmailInput(
        attrs={'class': 'form-control', 'placeholder': 'example@example.com'}))
    error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
        'username_exist': _("The username already exists. Please try another one."),
        'email_exist': _("The email already exists. Please try another one.")
    }
    password1 = forms.CharField(label=_("Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label=_("Password confirmation"),
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username']
        widgets ={
            'username': forms.TextInput(
                attrs={'class':"form-control",
                       'placeholder':'Name'}
            ),
        }

    def clean_username(self):
        try:
            user = User.objects.get(username=self.cleaned_data['username'])
        except User.DoesNotExist:
            return self.cleaned_data['username']
        raise forms.ValidationError(
            self.error_messages['username_exist'],
            code='username_exist',
        )

    def clean_email(self):
        try:
            user = User.objects.get(email=self.cleaned_data['email'])
        except User.DoesNotExist:
            return self.cleaned_data['email']
        raise forms.ValidationError(
            self.error_messages['email_exist'],
            code='email_exist',
        )

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )
        return password2

    def save(self, commit=True):
        user = super(UserRegistrationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user

    def get_user(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password1')
        user = authenticate(username=username, password=password)
        return user
