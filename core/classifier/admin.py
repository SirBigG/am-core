from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Area, Category, CategoryAIProfile, Country, Location, Region


class CategoryAIProfileInline(admin.StackedInline):
    model = CategoryAIProfile
    extra = 0
    max_num = 1
    fields = ("title", "status", "is_ai_enabled", "content", "sources", "internal_notes", "updated_by", "updated")
    readonly_fields = ("updated_by", "updated")


class CategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    list_display = ("tree_actions", "indented_title", "slug", "is_active", "is_diary_species_parent")
    list_filter = ("is_active", "is_diary_species_parent", "is_for_user")
    search_fields = ["value", "slug"]
    inlines = (CategoryAIProfileInline,)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for obj in instances:
            if isinstance(obj, CategoryAIProfile):
                obj.updated_by = request.user
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(CategoryAIProfile)
class CategoryAIProfileAdmin(admin.ModelAdmin):
    list_display = ("category", "title", "status", "is_ai_enabled", "updated")
    list_filter = ("status", "is_ai_enabled", "category__is_active", "category__is_diary_species_parent")
    search_fields = ("category__value", "category__slug", "title", "content")
    autocomplete_fields = ("category",)
    readonly_fields = ("created", "updated", "updated_by")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "category",
                    "title",
                    "status",
                    "is_ai_enabled",
                    "content",
                    "sources",
                    "internal_notes",
                )
            },
        ),
        ("Audit", {"fields": ("updated_by", "created", "updated")}),
    )

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


class LocationAdmin(admin.ModelAdmin):
    list_display = ("value", "longitude", "latitude", "region", "area")
    list_filter = ("region", "area")
    search_fields = ("value",)


admin.site.register(Location, LocationAdmin)
admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
admin.site.register(Category, CategoryAdmin)
