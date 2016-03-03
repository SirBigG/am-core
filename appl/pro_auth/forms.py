# -*- coding: utf-8 -*-

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.utils.translation import ugettext_lazy as _

from appl.pro_auth.models import User

from appl.classifier.models import Location

from phonenumber_field.formfields import PhoneNumberField

from dal import autocomplete


class UserCreationForm(forms.ModelForm):
    """
    A form that create a user, with no privileges.
    """
    error_messages = {
        'password_mismatch': _("The two password fields didn't match."),
    }
    password1 = forms.CharField(label=_("Password"),
                                widget=forms.PasswordInput)
    password2 = forms.CharField(label=_("Password confirmation"),
                                widget=forms.PasswordInput,
                                help_text=_("Enter the same password as before, for verification."))
    phone1 = PhoneNumberField(label=_("Phone 1"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'."
                                          "This field is required."))
    phone2 = PhoneNumberField(required=False,
                              label=_("Phone 2"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'"))
    phone3 = PhoneNumberField(required=False,
                              label=_("Phone 3"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'"))
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete'),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'birth_date', 'avatar',)

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


class UserAdminChangeForm(forms.ModelForm):
    """
    A form for change custom user data in admin site.
    """
    password = ReadOnlyPasswordHashField(label=_("Password"))
    phone1 = PhoneNumberField(label=_("Phone 1"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'"))
    phone2 = PhoneNumberField(required=False,
                              label=_("Phone 2"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'"))
    phone3 = PhoneNumberField(required=False,
                              label=_("Phone 3"),
                              help_text=_("Enter phone in International format. Example: '+380991234567'"))
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete'),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))

    class Meta:
        model = User
        fields = '__all__'

    def clean_password(self):
        # Regardless of what the user provides, return the initial value.
        # This is done here, rather than on the field, because the
        # field does not have access to the initial value
        return self.initial["password"]
