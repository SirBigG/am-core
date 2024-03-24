from dal import autocomplete
from django import forms
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _
from mptt.forms import TreeNodeChoiceField

from ..classifier.models import Category, Location
from ..posts.models import Post
from .models import Company, Link, Product


class ProductForm(forms.ModelForm):
    post = forms.ModelChoiceField(
        queryset=Post.objects.all(),
        widget=autocomplete.ModelSelect2(url="post-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select post from list."),
        label=_("Пост"),
        required=False,
    )
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(),
        help_text=_("Please select category from list."),
        label=_("Категорія"),
        required=False,
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "price",
            "description",
            "post",
            "category",
            "link",
            "active",
            "currency",
            "auction_price",
        ]
        widgets = {
            "description": Textarea(attrs={"cols": 40, "rows": 2}),
        }


class CompanyForm(forms.ModelForm):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=autocomplete.ModelSelect2(url="location-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select city from list."),
        label=_("Локація"),
    )

    class Meta:
        model = Company
        fields = "__all__"


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        return result


class AdminParseForm(forms.Form):
    url = forms.URLField(label=_("URL"), help_text=_("URL for parsing"), required=False)
    files = MultipleFileField(label=_("Files"), required=False)
    custom_parser_map = forms.JSONField(
        label=_("Custom parser map"),
        help_text=_("Custom parser map for parsing"),
        required=False,
    )
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(),
        help_text=_("Please select category from list."),
        label=_("Категорія"),
        required=False,
    )

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("url") and not cleaned_data.get("files"):
            raise forms.ValidationError(_("Please select URL or HTML file."))
        return cleaned_data


class LinkForm(forms.ModelForm):
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(),
        help_text=_("Please select category from list."),
        label=_("Категорія"),
        required=False,
    )

    class Meta:
        model = Link
        fields = "__all__"
