from django.forms import ModelForm, TextInput, Textarea

from appl.services.models import Feedback


class FeedbackForm(ModelForm):
    class Meta:
        model = Feedback
        fields = '__all__'
        widgets = {
            'title': TextInput(attrs={'class': 'form-control input-lg'}),
            'email': TextInput(attrs={'class': 'form-control input-lg'}),
            'text': Textarea(attrs={'class': 'form-control input-lg',
                                    'cols': 60, 'rows': 6})
        }
