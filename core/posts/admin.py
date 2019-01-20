from django.contrib import admin
from django import forms

from .models import Post, Photo, Comment, ParsedMap, Link, ParsedPost, PostView

from core.classifier.models import Category

from core.posts.parser.handler import ParseHandler

from modeltranslation.admin import TranslationAdmin, TranslationTabularInline


class PhotoInLine(TranslationTabularInline):
    model = Photo


class AdminPostForm(forms.ModelForm):
    rubric = forms.ModelChoiceField(queryset=Category.objects.filter(level=2))

    class Meta:
        model = Post
        fields = '__all__'


class CategoryFilter(admin.SimpleListFilter):
    title = 'category'
    parameter_name = 'category'

    def lookups(self, request, model_admin):
        return ((i.pk, i.value) for i in Category.objects.filter(level=2))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(rubric_id=self.value())


def activate_posts(modelsadmin, request, queryset):
    queryset.update(status=True)


activate_posts.short_description = "Activate selected posts"


class PostAdmin(TranslationAdmin):
    form = AdminPostForm
    inlines = [
        PhotoInLine,
    ]
    list_display = ('title', 'publisher', 'publish_date', 'hits', 'status', )
    readonly_fields = ('slug', )
    raw_id_fields = ('publisher',)
    list_filter = (CategoryFilter, 'status',)
    actions = [activate_posts]

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


def parse_links(modelsadmin, request, queryset):
    for i in queryset:
        ParseHandler(i).create_links()


parse_links.short_description = "Parse links from map"


def parse_posts(modelsadmin, request, queryset):
    for i in queryset:
        ParseHandler(i).create_posts()


parse_posts.short_description = "Parse posts from map"


class ParsedMapAdmin(admin.ModelAdmin):
    list_display = ('host', 'link', 'type')
    actions = [parse_links, parse_posts]


class PostViewAdmin(admin.ModelAdmin):
    list_display = ('fingerprint', 'post_id', 'user_id')


admin.site.register(Post, PostAdmin)
admin.site.register(Comment)
admin.site.register(ParsedMap, ParsedMapAdmin)
admin.site.register(ParsedPost, ParsedPostAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(PostView, PostViewAdmin)
