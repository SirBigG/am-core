from django.contrib import admin

from core.diary.models import Diary, DiaryItem, Plant


class DiaryItemInline(admin.TabularInline):
    model = DiaryItem
    extra = 0
    fields = ("action_type", "harvest_amount", "harvest_unit", "date", "created", "image")
    readonly_fields = ("created",)


@admin.register(Diary)
class DiaryAdmin(admin.ModelAdmin):
    inlines = (DiaryItemInline,)
    list_display = ("title", "user", "public", "plant_date", "updated", "created")
    list_filter = ("public", "plant_type", "created")
    search_fields = ("title", "description", "user__email")
    autocomplete_fields = ("user",)
    filter_horizontal = ("plants",)
    date_hierarchy = "plant_date"


@admin.register(DiaryItem)
class DiaryItemAdmin(admin.ModelAdmin):
    list_display = ("diary", "action_type", "harvest_summary", "date", "created")
    list_filter = ("action_type", "date", "created")
    search_fields = ("diary__title", "description", "diary__user__email")
    autocomplete_fields = ("diary",)
    filter_horizontal = ("plants",)
    date_hierarchy = "date"


@admin.register(Plant)
class PlantAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "category", "status", "plant_date", "created")
    list_filter = ("category", "status", "created")
    search_fields = ("title", "variety", "description", "user__email", "category__value")
    autocomplete_fields = ("user", "category")
    date_hierarchy = "plant_date"
