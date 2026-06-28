from dal import autocomplete
from django import forms
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _
from mptt.forms import TreeNodeChoiceField

from ..classifier.models import Category, Location
from ..posts.models import Post
from .models import Company, Link, Product


class ParserMapFormMixin(forms.ModelForm):
    parser_name_xpath = forms.CharField(
        label=_("Product name XPath"),
        help_text=_("XPath selector for parsed product names."),
        required=False,
        widget=Textarea(attrs={"cols": 100, "rows": 3, "style": "font-family: monospace; width: 90%;"}),
    )
    parser_price_xpath = forms.CharField(
        label=_("Product price XPath"),
        help_text=_("XPath selector for parsed product prices."),
        required=False,
        widget=Textarea(attrs={"cols": 100, "rows": 3, "style": "font-family: monospace; width: 90%;"}),
    )

    parser_map_fields = {
        "parser_name_xpath": "name",
        "parser_price_xpath": "price",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        parser_map = self.instance.parser_map or {}
        for field_name, parser_key in self.parser_map_fields.items():
            self.fields[field_name].initial = parser_map.get(parser_key, "")

    def clean(self):
        cleaned_data = super().clean()
        has_name = bool(cleaned_data.get("parser_name_xpath"))
        has_price = bool(cleaned_data.get("parser_price_xpath"))
        if has_name != has_price:
            raise forms.ValidationError(_("Provide both product name and price XPath selectors."))
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        parser_map = dict(instance.parser_map or {})
        for field_name, parser_key in self.parser_map_fields.items():
            value = self.cleaned_data.get(field_name)
            if value:
                parser_map[parser_key] = value
            else:
                parser_map.pop(parser_key, None)
        instance.parser_map = parser_map or None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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


class CompanyForm(ParserMapFormMixin, forms.ModelForm):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=autocomplete.ModelSelect2(url="location-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select city from list."),
        label=_("Локація"),
    )

    class Meta:
        model = Company
        exclude = ["parser_map"]


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


class LinkForm(ParserMapFormMixin, forms.ModelForm):
    category = TreeNodeChoiceField(
        queryset=Category.objects.all(),
        help_text=_("Please select category from list."),
        label=_("Категорія"),
        required=False,
    )

    class Meta:
        model = Link
        exclude = ["parser_map"]
