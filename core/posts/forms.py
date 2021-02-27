from django import forms
from django.utils.translation import ugettext_lazy as _

from ckeditor.widgets import CKEditorWidget

from core.classifier.models import Category

from .models import Post, Photo


class PostForm(forms.ModelForm):
    image1 = forms.ImageField(required=False, label=_('Фото'))
    image2 = forms.ImageField(required=False, label=_('Фото 2'))
    image3 = forms.ImageField(required=False, label=_('Фото 3'))
    image4 = forms.ImageField(required=False, label=_('Фото 4'))

    class Meta:
        model = Post
        fields = ["title", "text", "author", "source", "image1", "image2", "image3", "image4"]

        image_fields = ["image1", "image2", "image3", "image4"]

        labels = {
            'title': _('Заголовок'),
            'text': _('Текст'),
            'author': _('Автор'),
            'source': _('Джерело'),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            if name != "location":
                field.widget.attrs['class'] = "form-control"

    def create_images(self, commit=True):
        images = []
        for field_name in self.Meta.image_fields:
            image = self.cleaned_data.pop(field_name)
            if image:
                images.append(image)
        instance = super().save(commit=commit)
        if images:
            for i in images:
                Photo.objects.create(image=i, post=instance)
        return instance

    def save(self, commit=True):
        # todo: fix this bad thing in future
        self.instance.publisher_id = 1
        self.instance.status = False
        self.instance.rubric_id = 2429
        # self.instance.rubric_id = 1468
        instance = self.create_images(commit)
        return instance


class ProfileAddPostForm(PostForm):
    image1 = forms.ImageField(label=_('Фото'))
    rubric = forms.ModelChoiceField(queryset=Category.objects.filter(level=1).order_by("value"))

    class Meta:
        model = Post
        fields = ["rubric", "title", "text", "author", "source", "image1", "image2", "image3", "image4"]

        image_fields = ["image1", "image2", "image3", "image4"]

        labels = {
            'rubric': _("Категорія"),
            'title': _('Заголовок'),
            'text': _('Текст'),
            'author': _('Автор'),
            'source': _('Джерело'),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def clean_rubric(self):
        user_rubric, _ = Category.objects.get_or_create(defaults={"slug": "%s-user" % self.cleaned_data["rubric"].slug},
                                                        **{"parent": self.cleaned_data["rubric"],
                                                           "value": "Статті користувачів"})
        return user_rubric

    def save(self, commit=True):
        self.instance.publisher = self.request.user
        instance = self.create_images(commit)
        return instance


class UpdatePostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "text", "author", "source"]

    labels = {
        'title': _('Заголовок'),
        'text': _('Текст'),
        'author': _('Автор'),
        'source': _('Джерело'),
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text"].widget = CKEditorWidget(config_name="public")
        for name, field in self.fields.items():
            if name != "location":
                field.widget.attrs['class'] = "form-control"


class PhotoForm(forms.ModelForm):
    post_id = forms.IntegerField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs['class'] = "form-control"

    class Meta:
        model = Photo
        fields = ['image', 'description', 'author', 'post_id']

        labels = {
            'image': _("Фото (обов'язкове)"),
            'description': _('Короткий опис'),
            'author': _('Автор'),
        }

    def save(self, commit=True):
        self.instance.post_id = self.initial.get('post_id')
        return super().save()
