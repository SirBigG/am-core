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
    raw_id_fields = ('publisher',)

    def get_form(self, request, obj=None, **kwargs):
        form = super(PostAdmin, self).get_form(request, obj, **kwargs)
        form.base_fields['publisher'].initial = request.user
        return form


class LinkAdmin(admin.ModelAdmin):
    list_display = ('link', 'is_parsed')


class AdminParsedPostForm(forms.ModelForm):
    rubric = forms.ModelChoiceField(queryset=Category.objects.filter(level=2))

    class Meta:
        model = ParsedPost
        fields = '__all__'


class ParsedPostAdmin(admin.ModelAdmin):
    form = AdminParsedPostForm
    list_display = ('title', 'original', 'is_processed', 'is_translated', 'is_finished',)
    raw_id_fields = ('publisher',)
    readonly_fields = ('hash',)
    list_filter = ('is_processed', 'is_translated', 'is_finished',)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['publisher'].initial = request.user
        return form


admin.site.register(Post, PostAdmin)
admin.site.register(Comment)
admin.site.register(ParsedMap)
admin.site.register(ParsedPost, ParsedPostAdmin)
admin.site.register(Link, LinkAdmin)
