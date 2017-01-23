from django import forms

from core.services.models import Feedback


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = '__all__'
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control input-lg'}),
            'email': forms.TextInput(attrs={'class': 'form-control input-lg'}),
            'text': forms.Textarea(attrs={'class': 'form-control input-lg',
                                          'cols': 60, 'rows': 6})
        }
