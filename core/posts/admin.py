from django.contrib import admin
from django import forms
from django.db.models import Count

from .models import Post, Photo, ParsedMap, Link, ParsedPost, PostView, UsefulStatistic, SearchStatistic

from core.classifier.models import Category

from dal import autocomplete


class PhotoInLine(admin.TabularInline):
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


class HasPhotoFilter(admin.SimpleListFilter):
    title = 'has photo'
    parameter_name = 'has_photo'

    def lookups(self, request, model_admin):
        return (True, 'Has photo'), (False, 'No photo')

    def queryset(self, request, queryset):
        if self.value():
            if self.value() is True:
                return queryset.annotate(photo_count=Count('photo')).filter(photo_count__gt=0)
            else:
                return queryset.annotate(photo_count=Count('photo')).filter(photo_count=0)


def activate_posts(modelsadmin, request, queryset):
    queryset.update(status=True)


activate_posts.short_description = "Activate selected posts"


class TestTaggit(autocomplete.TaggitSelect2):
    def format_value(self, value):
        if not value:
            return []
        values = set()
        for v in value:
            if not v:
                continue

            values.add(self.option_value(v))
        return values

    def options(self, name, value, attrs=None):
        """Return only select options."""
        # When the data hasn't validated, we get the raw input
        if isinstance(value, str):
            value = value.split(',')

        for v in value:
            if not v:
                continue

            real_values = v.split(',') if hasattr(v, 'split') else v
            if real_values is not list:
                real_values = [real_values]
            for rv in real_values:
                yield self.option_value(rv)


class PostAdmin(admin.ModelAdmin):
    form = AdminPostForm
    inlines = [
        PhotoInLine,
    ]
    list_display = ('title', 'publisher', 'publish_date', 'hits', 'status', 'tag_list', 'has_photo')
    readonly_fields = ('slug', 'hits', 'absolute_url',)
    raw_id_fields = ('publisher',)
    list_filter = (CategoryFilter, HasPhotoFilter, 'status')
    actions = [activate_posts]

    fieldsets = (
        ("Main data", {
            'fields': ('title', 'text', 'status', 'rubric')
        }),
        (None, {
           'fields': ('tags',)
        }),
        ("Extra data", {
           'fields': ('country', 'meta', 'meta_description')
        }),
        ('Advanced options', {
            'classes': ('collapse',),
            'fields': ('work_status', 'author', 'source', 'publisher', 'publish_date', 'hits', 'slug', 'absolute_url'),
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields['publisher'].initial = request.user
        # print(form.base_fields)
        # form.base_fields['tags'].widget = autocomplete.TaggitSelect2('/taggit-autocomplete/')
        form.base_fields['tags'].widget = TestTaggit('/taggit-autocomplete/')
        form.base_fields['tags'].required = False
        return form

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    def has_photo(self, obj):
        return obj.photo.count() > 0


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


class ParsedMapAdmin(admin.ModelAdmin):
    list_display = ('host', 'link', 'type')


class PostViewAdmin(admin.ModelAdmin):
    list_display = ('fingerprint', 'post_id', 'user_id', 'created')


class UsefulStatisticAdmin(admin.ModelAdmin):
    list_display = ('fingerprint', 'post_id', 'user_id', 'is_useful', 'created')


class SearchStatisticAdmin(admin.ModelAdmin):
    list_display = ('fingerprint', 'search_phrase', 'created')


class PhotoAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'description',)
    raw_id_fields = ('post',)

    def title(self, obj):
        return obj.post.title

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Post, PostAdmin)
admin.site.register(ParsedMap, ParsedMapAdmin)
admin.site.register(ParsedPost, ParsedPostAdmin)
admin.site.register(Link, LinkAdmin)
admin.site.register(PostView, PostViewAdmin)
admin.site.register(Photo, PhotoAdmin)
admin.site.register(UsefulStatistic, UsefulStatisticAdmin)
admin.site.register(SearchStatistic, SearchStatisticAdmin)


# setup admin site headers
admin.site.site_header = 'AgroMega'
admin.site.site_title = 'AgroMega'
