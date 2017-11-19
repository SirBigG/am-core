from django import forms
from django.utils.translation import ugettext_lazy as _

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
