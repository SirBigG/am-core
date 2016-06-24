# -*- coding: utf-8 -*-

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.translation import ugettext_lazy as _

from appl.pro_auth.models import User

from appl.classifier.models import Location

from phonenumber_field.formfields import PhoneNumberField

from dal import autocomplete

from captcha.fields import ReCaptchaField


class UserCreationForm(forms.ModelForm):
    """
    A form that create a user, with no privileges.
    """
    error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
    }
    password1 = forms.CharField(label=_("Password"),
                                widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(label=_("Password confirmation"),
                                widget=forms.PasswordInput(attrs={'class': 'form-control'}),
                                help_text=_("Enter the same password as before, for verification."))
    phone1 = PhoneNumberField(label=_("Phone"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'."
                                          "This field is required."),
                              widget=forms.TextInput(attrs={'class': 'form-control'}))

    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete',
                                                                       attrs={'class': 'form-control'}),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))
    captcha = ReCaptchaField(label=_("Captcha"))

    class Meta:
        model = User
        fields = ['email', 'phone1', 'location', 'password1', 'password2', 'captcha']
        widgets = {
            'email': forms.TextInput(attrs={'class': 'form-control'})
        }

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                self.error_messages['password_mismatch'],
                code='password_mismatch',
            )
        self.instance.username = self.cleaned_data.get('username')
        password_validation.validate_password(self.cleaned_data.get('password2'), self.instance)
        return password2

    def save(self, commit=True):
        """Save the provided password in hashed format."""
        user = super(UserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class AdminUserChangeForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField(
        label=_("Password"),
        help_text=_("Raw passwords are not stored, so there is no way to see "
                    "this user's password, but you can change the password "
                    "using <a href=\"../password/\">this form</a>."))
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete',
                                                                       attrs={'class': 'form-control'}),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))

    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super(AdminUserChangeForm, self).__init__(*args, **kwargs)
        f = self.fields.get('user_permissions')
        if f is not None:
            f.queryset = f.queryset.select_related('content_type')

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial["password"]
