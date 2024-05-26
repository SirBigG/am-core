from dal import autocomplete
from django import forms
from django.contrib import admin
from django.contrib.postgres.forms import SimpleArrayField
from django.db.models import Count
from mptt.admin import TreeRelatedFieldListFilter
from mptt.forms import TreeNodeChoiceField

from core.classifier.models import Category

from .models import Photo, Post, SearchStatistic, UsefulStatistic


class PhotoInLine(admin.TabularInline):
    model = Photo


class AdminPostForm(forms.ModelForm):
    rubric = TreeNodeChoiceField(queryset=Category.objects.all())
    sources = SimpleArrayField(
        forms.URLField(), required=False, widget=forms.Textarea, help_text="Enter sources separated by commas"
    )

    class Meta:
        model = Post
        fields = "__all__"


class CategoryFilter(admin.SimpleListFilter):
    title = "category"
    parameter_name = "category"

    def lookups(self, request, model_admin):
        return ((i.pk, i.value) for i in Category.objects.filter(level=2))

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(rubric_id=self.value())


class HasPhotoFilter(admin.SimpleListFilter):
    title = "has photo"
    parameter_name = "has_photo"

    def lookups(self, request, model_admin):
        return (True, "Has photo"), (False, "No photo")

    def queryset(self, request, queryset):
        if self.value():
            if self.value() is True:
                return queryset.annotate(photo_count=Count("photo")).filter(photo_count__gt=0)
            else:
                return queryset.annotate(photo_count=Count("photo")).filter(photo_count=0)


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
            value = value.split(",")

        for v in value:
            if not v:
                continue

            real_values = v.split(",") if hasattr(v, "split") else v
            if real_values is not list:
                real_values = [real_values]
            for rv in real_values:
                yield self.option_value(rv)


class PostAdmin(admin.ModelAdmin):
    form = AdminPostForm
    inlines = [
        PhotoInLine,
    ]
    list_display = ("title", "publisher", "hits", "publish_date", "update_date", "status", "has_photo")
    readonly_fields = (
        "slug",
        "hits",
        "absolute_url",
    )
    raw_id_fields = ("publisher",)
    list_filter = (("rubric", TreeRelatedFieldListFilter), HasPhotoFilter, "status")
    actions = [activate_posts]
    search_fields = (
        "title",
        "text",
    )

    fieldsets = (
        ("Main data", {"fields": ("title", "text", "rubric", "country", "sources")}),
        (None, {"fields": ("tags",)}),
        ("Metadata", {"fields": ("meta", "meta_description")}),
        (
            "Advanced options",
            {
                "classes": ("collapse",),
                "fields": (
                    "status",
                    "update_date",
                    "work_status",
                    "author",
                    "publisher",
                    "publish_date",
                    "hits",
                    "slug",
                    "absolute_url",
                ),
            },
        ),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["publisher"].initial = request.user
        # print(form.base_fields)
        # form.base_fields['tags'].widget = autocomplete.TaggitSelect2('/taggit-autocomplete/')
        form.base_fields["tags"].widget = TestTaggit("/taggit-autocomplete/")
        form.base_fields["tags"].required = False
        return form

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    def has_photo(self, obj):
        return obj.photo.count() > 0


class UsefulStatisticAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "post_id", "user_id", "is_useful", "created")


class SearchStatisticAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "search_phrase", "created")


class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "description",
    )
    raw_id_fields = ("post",)

    def title(self, obj):
        return obj.post.title


admin.site.register(Post, PostAdmin)
admin.site.register(Photo, PhotoAdmin)
admin.site.register(UsefulStatistic, UsefulStatisticAdmin)
admin.site.register(SearchStatistic, SearchStatisticAdmin)


# setup admin site headers
admin.site.site_header = "AgroMega"
admin.site.site_title = "AgroMega"
