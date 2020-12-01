from django import forms
from django.utils.translation import gettext_lazy as _

from ckeditor.widgets import CKEditorWidget

from core.classifier.models import Category

from .models import Advert


class AdvertForm(forms.ModelForm):
    author = forms.CharField(required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.filter(level=1).order_by("value"), required=False)

    class Meta:
        model = Advert
        fields = ["title", "description", "category", "author", "contact", "image"]

        labels = {
            'title': _('Заголовок'),
            'description': _('Текст'),
            'author': _('Автор'),
            'contact': _('Контакти'),
            'image': _('Картинка')
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            field.widget.attrs['class'] = "form-control"
