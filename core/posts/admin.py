import json

from ckeditor.widgets import CKEditorWidget
from dal import autocomplete
from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from mptt.admin import TreeRelatedFieldListFilter
from mptt.forms import TreeNodeChoiceField

from core.classifier.models import Category

from .category_attributes import (
    attribute_form_field_name,
    build_form_field,
    get_category_attributes_for_post,
    get_category_schema_fields,
    normalize_attribute_value,
    range_value_to_display,
    rebuild_post_attribute_values,
    set_category_attributes_for_post,
)
from .models import (
    CategoryAttributeChoice,
    CategoryAttributeField,
    CategoryAttributeFieldType,
    CategoryAttributeGroup,
    Photo,
    Post,
    PostAttributeValue,
    SearchStatistic,
    UsefulStatistic,
)


class PhotoInLine(admin.TabularInline):
    model = Photo


class AdminPostForm(forms.ModelForm):
    rubric = TreeNodeChoiceField(queryset=Category.objects.all())
    category_attribute_fields = ()

    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sources"].widget = CKEditorWidget()
        self.category_attribute_fields = tuple(self.__class__.category_attribute_fields)
        rubric_id = self._selected_rubric_id()
        category_attributes = get_category_attributes_for_post(self.instance, rubric_id)
        for field in self.category_attribute_fields:
            field_name = attribute_form_field_name(field)
            self.fields[field_name] = build_form_field(field)
            initial = category_attributes.get(field.key)
            if field.field_type == CategoryAttributeFieldType.RANGE:
                initial = range_value_to_display(initial)
            self.fields[field_name].initial = initial

    def clean(self):
        cleaned_data = super().clean()
        self.cleaned_category_attributes = {}
        selected_rubric = self.cleaned_data.get("rubric")
        if not selected_rubric:
            return cleaned_data
        for field in self.category_attribute_fields:
            field_name = attribute_form_field_name(field)
            try:
                value = normalize_attribute_value(field, cleaned_data.get(field_name))
            except forms.ValidationError as error:
                self.add_error(field_name, error)
                continue
            self.cleaned_category_attributes[field.key] = value
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_rubric = self.cleaned_data.get("rubric")
        if selected_rubric:
            category_values = get_category_attributes_for_post(instance, selected_rubric.pk)
            for field in self.category_attribute_fields:
                value = self.cleaned_category_attributes.get(field.key)
                if value in (None, "", [], ()):
                    category_values.pop(field.key, None)
                else:
                    category_values[field.key] = value
            set_category_attributes_for_post(instance, selected_rubric.pk, category_values)
        if commit:
            instance.save()
            self.save_m2m()
            rebuild_post_attribute_values(instance)
        return instance

    def _selected_rubric_id(self):
        if self.is_bound:
            return self.data.get(self.add_prefix("rubric"))
        return self.instance.rubric_id


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


@admin.action(description="Activate selected posts")
def activate_posts(modelsadmin, request, queryset):
    queryset.update(status=True)


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


@admin.register(Post)
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
        "stored_category_attributes",
    )
    raw_id_fields = ("publisher",)
    list_filter = (("rubric", TreeRelatedFieldListFilter), HasPhotoFilter, "status")
    actions = [activate_posts]
    search_fields = (
        "title",
        "text",
    )

    def get_fieldsets(self, request, obj=None):
        fieldsets = [
            ("Main data", {"fields": ("title", "text", "rubric", "country", "sources")}),
            (None, {"fields": ("tags",)}),
        ]
        fieldsets.extend(self.get_category_attribute_fieldsets(request, obj))
        fieldsets.extend(
            [
                ("Metadata", {"fields": ("meta", "meta_description")}),
                (
                    "Stored category attributes",
                    {
                        "classes": ("collapse",),
                        "fields": ("stored_category_attributes",),
                    },
                ),
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
            ]
        )
        return tuple(fieldsets)

    def get_form(self, request, obj=None, **kwargs):
        attribute_fields = tuple(self.get_category_attribute_fields(request, obj))
        form_attrs = {"category_attribute_fields": attribute_fields}
        for field in attribute_fields:
            form_attrs[attribute_form_field_name(field)] = build_form_field(field)
        form_class = type(
            "DynamicAdminPostForm",
            (AdminPostForm,),
            form_attrs,
        )
        kwargs["form"] = form_class
        form = super().get_form(request, obj, **kwargs)
        form.base_fields["publisher"].initial = request.user
        # print(form.base_fields)
        # form.base_fields['tags'].widget = autocomplete.TaggitSelect2('/taggit-autocomplete/')
        form.base_fields["tags"].widget = TestTaggit("/taggit-autocomplete/")
        form.base_fields["tags"].required = False
        return form

    def get_category_attribute_fields(self, request, obj=None):
        rubric_id = request.POST.get("rubric")
        if not rubric_id and obj:
            rubric_id = obj.rubric_id
        return list(get_category_schema_fields(rubric_id))

    def get_category_attribute_fieldsets(self, request, obj=None):
        field_names = tuple(
            attribute_form_field_name(field) for field in self.get_category_attribute_fields(request, obj)
        )
        if not field_names:
            return []
        return [
            (
                "Category attributes",
                {
                    "classes": ("collapse", "category-attributes"),
                    "fields": field_names,
                    "description": "Fields are grouped and ordered by the selected category schema.",
                },
            )
        ]

    def tag_list(self, obj):
        return ", ".join(o.name for o in obj.tags.all())

    def has_photo(self, obj):
        return obj.photo.count() > 0

    def stored_category_attributes(self, obj):
        if not obj or not obj.pk:
            return "-"
        return format_html("<pre>{}</pre>", json.dumps(obj.category_attributes or {}, ensure_ascii=False, indent=2))

    class Media:
        css = {"all": ("posts/admin/ckeditor-source.css",)}
        js = ("posts/admin/ckeditor-source.js",)


class CategoryAttributeChoiceInline(admin.TabularInline):
    model = CategoryAttributeChoice
    extra = 0
    fields = ("value", "label", "is_active", "is_public", "sort_order")


@admin.register(CategoryAttributeField)
class CategoryAttributeFieldAdmin(admin.ModelAdmin):
    list_display = (
        "label",
        "category",
        "group",
        "key",
        "field_type",
        "is_active",
        "is_filterable",
        "is_public",
        "sort_order",
    )
    list_filter = ("field_type", "is_active", "is_filterable", "is_public", "category")
    search_fields = ("label", "key", "category__value")
    autocomplete_fields = ("category", "group")
    inlines = [CategoryAttributeChoiceInline]


@admin.register(CategoryAttributeGroup)
class CategoryAttributeGroupAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_active", "sort_order")
    list_filter = ("is_active", "category")
    search_fields = ("title", "category__value")
    autocomplete_fields = ("category",)


@admin.register(CategoryAttributeChoice)
class CategoryAttributeChoiceAdmin(admin.ModelAdmin):
    list_display = ("label", "value", "field", "is_active", "is_public", "sort_order")
    list_filter = ("is_active", "is_public", "field__category")
    search_fields = ("label", "value", "field__label")


@admin.register(PostAttributeValue)
class PostAttributeValueAdmin(admin.ModelAdmin):
    list_display = (
        "post",
        "category",
        "field",
        "choice",
        "value_text",
        "value_number",
        "value_number_min",
        "value_number_max",
        "value_boolean",
    )
    list_filter = ("category", "field")
    raw_id_fields = ("post",)


@admin.register(UsefulStatistic)
class UsefulStatisticAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "post_id", "user_id", "is_useful", "created")


@admin.register(SearchStatistic)
class SearchStatisticAdmin(admin.ModelAdmin):
    list_display = ("fingerprint", "search_phrase", "created")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "author",
        "description",
    )
    raw_id_fields = ("post",)

    def title(self, obj):
        return obj.post.title


# setup admin site headers
admin.site.site_header = "AgroMega"
admin.site.site_title = "AgroMega"
