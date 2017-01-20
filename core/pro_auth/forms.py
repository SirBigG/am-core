from __future__ import unicode_literals

from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import ReadOnlyPasswordHashField, AuthenticationForm
from django.utils.translation import ugettext_lazy as _

from core.pro_auth.models import User

from core.classifier.models import Location

from phonenumber_field.formfields import PhoneNumberField

from dal import autocomplete

from captcha.fields import ReCaptchaField


class AdminUserCreationForm(forms.ModelForm):
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

    class Meta:
        model = User
        fields = ['email', 'phone1', 'location', 'password1', 'password2']
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
        user = super(AdminUserCreationForm, self).save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserCreationForm(AdminUserCreationForm):
    captcha = ReCaptchaField(label=_("Captcha"))

    class Meta(AdminUserCreationForm.Meta):
        fields = ['email', 'phone1', 'location', 'password1', 'password2', 'captcha']


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


class UserChangeForm(forms.ModelForm):
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete',
                                                                       attrs={'class': 'form-control'}),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))

    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'phone1', 'location',
                  'birth_date', 'avatar',)


class EmailConfirmForm(forms.Form):
    email = forms.EmailField()

    error_messages = {
        'not_user': _('Sorry, but user with this email does not found!')
    }

    def __init__(self, *args, **kwargs):
        self.user_cache = None
        super(EmailConfirmForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            try:
                self.user_cache = User.objects.get(email=email)
            except User.DoesNotExist:
                raise forms.ValidationError(
                    self.error_messages['not_user'],
                    code='not_user'
                )
        return email

    def get_user(self):
        return self.user_cache


class LoginForm(AuthenticationForm):
    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request=None, *args, **kwargs)
        self.fields['username'].widget.attrs['class'] = 'form-control'
        self.fields['password'].widget.attrs['class'] = 'form-control'
