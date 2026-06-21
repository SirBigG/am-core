from ckeditor.widgets import CKEditorWidget
from dal import autocomplete
from django import forms
from django.utils.translation import gettext_lazy as _

from core.classifier.models import Category, Location

from .models import Advert, AdvertImage, get_advert_max_photos


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super(MultipleImageField, self).clean(file, initial) for file in files]


class AdvertForm(forms.ModelForm):
    photos = MultipleImageField(
        required=False,
        label=_("Фото"),
        help_text=_("Можна додати до %(count)s фото. Перше фото буде показане в списку оголошень.")
        % {"count": get_advert_max_photos()},
        widget=MultipleFileInput(attrs={"multiple": True, "accept": "image/*", "class": "form-control"}),
    )
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
        fields = ["title", "photos", "description", "category", "author", "contact", "location", "price"]

        labels = {
            "title": _("Заголовок"),
            "description": _("Короткий опис"),
            "author": _("Автор"),
            "contact": _("Контакти"),
            "location": _("Місто/село"),
            "price": _("Ціна"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            if name != "location":
                field.widget.attrs["class"] = "form-control"

    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        existing_count = 0
        if self.instance and self.instance.pk:
            existing_count = self.instance.photos.count()
            if self.instance.image:
                existing_count += 1
        max_photos = get_advert_max_photos()
        if existing_count + len(photos) > max_photos:
            available = max(max_photos - existing_count, 0)
            raise forms.ValidationError(
                _("Можна додати не більше %(count)s фото. Зараз доступно: %(available)s.")
                % {"count": max_photos, "available": available}
            )
        return photos

    def save(self, commit=True):
        photos = self.cleaned_data.pop("photos", [])
        advert = super().save(commit=commit)
        if commit:
            for photo in photos:
                AdvertImage.objects.create(advert=advert, image=photo)
        return advert
