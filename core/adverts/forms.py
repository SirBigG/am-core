from ckeditor.widgets import CKEditorWidget
from dal import autocomplete
from django import forms
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _

from core.classifier.models import Category, Location

from .models import Advert, AdvertImage, get_advert_max_photos


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True

    def __init__(self, attrs=None, slots=5):
        self.slots = slots
        super().__init__(attrs)

    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        base_id = attrs.get("id")
        slots = []
        for index in range(max(self.slots, 0)):
            slot_attrs = attrs.copy()
            slot_attrs["data-advert-photo-slot"] = index + 1
            if base_id and index:
                slot_attrs["id"] = f"{base_id}_{index + 1}"
            input_html = super().render(name, value, slot_attrs, renderer)
            label_for = slot_attrs.get("id", "")
            slots.append(
                f'<div class="advert-photo-slot">'
                f"{input_html}"
                f'<label class="advert-photo-slot-button" for="{label_for}">'
                f'<span class="advert-photo-slot-icon"><i class="icon-plus"></i></span>'
                f'<span class="advert-photo-slot-text">Додати</span>'
                f'<span class="advert-photo-slot-filename" data-advert-photo-filename></span>'
                f"</label>"
                f"</div>"
            )
        return mark_safe(f'<div class="advert-photo-slots">{"".join(slots)}</div>')

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        return files.get(name)


class MultipleImageField(forms.ImageField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        return [super().clean(file, initial) for file in files]


class AdvertForm(forms.ModelForm):
    photos = MultipleImageField(
        required=False,
        label=_("Фото"),
        help_text=_("Можна додати до %(count)s фото. Перше фото буде показане в списку оголошень.")
        % {"count": get_advert_max_photos()},
        widget=MultipleFileInput(
            attrs={"multiple": True, "accept": "image/*", "class": "visually-hidden advert-photo-input"},
            slots=get_advert_max_photos(),
        ),
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
        self.fields["title"].help_text = _("Коротко опишіть, що продаєте або шукаєте.")
        self.fields["contact"].help_text = _("Ці контакти побачать користувачі, які зацікавляться оголошенням.")
        self.fields["price"].help_text = _("Вкажіть 0, якщо хочете домовлятися про ціну окремо.")
        self.fields["title"].widget.attrs.setdefault("placeholder", _("Наприклад: Саджанці яблуні Голден"))
        self.fields["author"].widget.attrs.setdefault("autocomplete", "name")
        self.fields["author"].widget.attrs.setdefault("placeholder", _("Ваше ім'я або назва господарства"))
        self.fields["contact"].widget.attrs.setdefault("autocomplete", "tel")
        self.fields["contact"].widget.attrs.setdefault("placeholder", _("Телефон, email або інший спосіб зв'язку"))
        self.fields["price"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["price"].widget.attrs.setdefault("min", "0")
        remaining_photos = self.remaining_photo_slots
        self.fields["photos"].widget.slots = remaining_photos
        if self.existing_photo_count:
            if remaining_photos:
                self.fields["photos"].help_text = _("Вже додано %(existing)s фото. Можна додати ще %(available)s.") % {
                    "existing": self.existing_photo_count,
                    "available": remaining_photos,
                }
            else:
                self.fields["photos"].help_text = _("Вже додано максимальну кількість фото.")
        for name, field in self.fields.items():
            if name not in {"location", "photos"}:
                field.widget.attrs["class"] = "form-control"

    @property
    def max_photos(self):
        return get_advert_max_photos()

    @property
    def existing_photo_count(self):
        if not self.instance or not self.instance.pk:
            return 0
        count = self.instance.photos.count()
        if self.instance.image:
            count += 1
        return min(count, self.max_photos)

    @property
    def remaining_photo_slots(self):
        return max(self.max_photos - self.existing_photo_count, 0)

    def clean_photos(self):
        photos = self.cleaned_data.get("photos", [])
        existing_count = self.existing_photo_count
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
