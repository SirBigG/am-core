from django.contrib import admin

from core.diary.models import Diary, DiaryItem


class DiaryItemInline(admin.TabularInline):
    model = DiaryItem
    extra = 0
    fields = ("action_type", "date", "created", "image")
    readonly_fields = ("created",)


@admin.register(Diary)
class DiaryAdmin(admin.ModelAdmin):
    inlines = (DiaryItemInline,)
    list_display = ("title", "user", "plant_type", "public", "plant_date", "created")
    list_filter = ("public", "plant_type", "created")
    search_fields = ("title", "description", "user__email")
    autocomplete_fields = ("user",)
    date_hierarchy = "plant_date"


@admin.register(DiaryItem)
class DiaryItemAdmin(admin.ModelAdmin):
    list_display = ("diary", "action_type", "date", "created")
    list_filter = ("action_type", "date", "created")
    search_fields = ("diary__title", "description", "diary__user__email")
    autocomplete_fields = ("diary",)
    date_hierarchy = "date"
