from dal import autocomplete
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import Product
from ..posts.models import Post


class ProductForm(forms.ModelForm):
    post = forms.ModelChoiceField(queryset=Post.objects.all(),
                                  widget=autocomplete.ModelSelect2(url='post-autocomplete',
                                                                   attrs={'class': 'form-control'}),
                                  help_text=_("Please select city from list."),
                                  label=_("Локація"),
                                  required=False)

    class Meta:
        model = Product
        fields = "__all__"
