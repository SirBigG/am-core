from dal import autocomplete
from django import forms
from django.forms import Textarea
from django.utils.translation import gettext_lazy as _

from ..classifier.models import Location
from ..posts.models import Post
from .models import Company, Product


class ProductForm(forms.ModelForm):
    post = forms.ModelChoiceField(
        queryset=Post.objects.all(),
        widget=autocomplete.ModelSelect2(url="post-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select post from list."),
        label=_("Пост"),
        required=False,
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "price",
            "description",
            "post",
            "link",
            "active",
            "currency",
            "auction_price",
        ]
        widgets = {
            "description": Textarea(attrs={"cols": 60, "rows": 2}),
        }


class CompanyForm(forms.ModelForm):
    location = forms.ModelChoiceField(
        queryset=Location.objects.all(),
        widget=autocomplete.ModelSelect2(url="location-autocomplete", attrs={"class": "form-control"}),
        help_text=_("Please select city from list."),
        label=_("Локація"),
        required=False,
    )

    class Meta:
        model = Company
        fields = "__all__"
