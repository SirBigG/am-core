from django import forms

from captcha.fields import ReCaptchaField

from core.services.models import Feedback


class FeedbackForm(forms.ModelForm):
    captcha = ReCaptchaField()

    class Meta:
        model = Feedback
        fields = ('title', 'email', 'text', 'captcha')
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control input-lg'}),
            'email': forms.TextInput(attrs={'class': 'form-control input-lg'}),
            'text': forms.Textarea(attrs={'class': 'form-control input-lg',
                                          'cols': 60, 'rows': 6})
        }
