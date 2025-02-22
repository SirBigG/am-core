from ckeditor.widgets import CKEditorWidget
from dal import autocomplete
from django import forms
from django.utils.translation import gettext_lazy as _

from core.classifier.models import Category, Location

from .models import Advert


class AdvertForm(forms.ModelForm):
    category = forms.ModelChoiceField(
        queryset=Category.objects.filter(level=1).order_by("value"), required=False, label=_("Категорія")
    )
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=autocomplete.ModelSelect2(url="location-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select city from list."),
        label=_("Локація"),
        required=False,
    )

    class Meta:
        model = Advert
        fields = ["title", "image", "description", "category", "author", "contact", "location", "price"]

        labels = {
            "title": _("Заголовок"),
            "description": _("Короткий опис"),
            "author": _("Автор"),
            "contact": _("Контакти"),
            "image": _("Картинка"),
            "location": _("Місто/село"),
            "price": _("Ціна"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            if name != "location":
                field.widget.attrs["class"] = "form-control"
