from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin, TreeRelatedFieldListFilter

from core.registry.models import Company, Variety, VarietyCategory


class VarietyCategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    pass


class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "original_name", "code", "country")
    list_filter = ("country",)
    search_fields = ("name", "original_name", "code")


class VarietyAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "title_original",
        "publication",
        "category",
        "application_number",
        "registration_year",
        "unregister_year",
        "unregister_date",
        "recommended_zone",
        "direction_of_use",
        "ripeness_group",
    )
    list_editable = ("publication",)
    autocomplete_fields = ("publication",)
    list_filter = (
        ("category", TreeRelatedFieldListFilter),
        "registration_year",
        "unregister_year",
        "excluded",
    )
    search_fields = ("title", "title_original", "application_number")


admin.site.register(Company, CompanyAdmin)
admin.site.register(Variety, VarietyAdmin)
admin.site.register(VarietyCategory, VarietyCategoryAdmin)
