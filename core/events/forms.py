from django import forms
from django.utils.translation import gettext_lazy as _

from ckeditor.widgets import CKEditorWidget

from dal import autocomplete

from core.classifier.models import Location

from .models import Event


class EventForm(forms.ModelForm):
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete',
                                                                       attrs={'class': 'form-control'}),
                                      help_text=_("Please select city from list."),
                                      label=_("City"))

    class Meta:
        model = Event
        fields = '__all__'


class EventAddForm(forms.ModelForm):
    location = forms.ModelChoiceField(queryset=Location.objects.all(),
                                      widget=autocomplete.ModelSelect2(url='location-autocomplete'),
                                      help_text=_("Please select city from list."),
                                      label=_("Населений пункт"))

    class Meta:
        model = Event
        fields = ["title", "text", "type", "poster", "address", "location", "start", "stop"]

        labels = {
            'title': _('Назва події'),
            'text': _(''),
            'type': _('Тип'),
            'poster': _('Картка події'),
            'address': _('Адреса'),
            'start': _('Дата початку'),
            'stop': _('Дата закінчення'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            if name != "location":
                field.widget.attrs['class'] = "form-control"

    def save(self, commit=True):
        # todo: fix this bad thing in future
        self.instance.user_id = 1
        return super().save(commit=commit)
