from django.contrib import admin
from django import forms

from .models import Post, Photo, Comment, ParsedMap, Link, ParsedPost
from core.classifier.models import Category

from modeltranslation.admin import TranslationAdmin, TranslationTabularInline


class PhotoInLine(TranslationTabularInline):
    model = Photo


class AdminPostForm(forms.ModelForm):
    rubric = forms.ModelChoiceField(queryset=Category.objects.filter(level=2))

    class Meta:
        model = Post
        fields = '__all__'


class PostAdmin(TranslationAdmin):
    form = AdminPostForm
    inlines = [
        PhotoInLine,
    ]
    list_display = ('title', 'publisher', 'publish_date', 'hits', 'status', )
    readonly_fields = ('slug', )

    def get_form(self, request, obj=None, **kwargs):
        form = super(PostAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['publisher'].initial = request.user
        return form

admin.site.register(Post, PostAdmin)
admin.site.register(Comment)
admin.site.register(ParsedMap)
admin.site.register(ParsedPost)
admin.site.register(Link)
