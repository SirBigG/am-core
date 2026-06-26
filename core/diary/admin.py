from django.contrib import admin

from core.diary.models import Diary, DiaryItem, Planner, PlannerArea, PlannerPlanting, PlannerTask, Plant


class PlannerAreaInline(admin.TabularInline):
    model = PlannerArea
    extra = 0
    fields = ("title", "area_type", "diary", "x_m", "y_m", "width_m", "height_m")


class PlannerPlantingInline(admin.TabularInline):
    model = PlannerPlanting
    extra = 0
    fields = ("plant", "mode", "status", "quantity", "rows", "occupied_area_m2", "x_pct", "y_pct", "notes")


class PlannerTaskInline(admin.TabularInline):
    model = PlannerTask
    extra = 0
    fields = ("title", "area", "due_date", "is_completed", "completed_at")


@admin.register(Planner)
class PlannerAdmin(admin.ModelAdmin):
    inlines = (PlannerAreaInline, PlannerTaskInline)
    list_display = ("title", "user", "width_m", "height_m", "updated")
    search_fields = ("title", "user__email")
    autocomplete_fields = ("user",)


@admin.register(PlannerArea)
class PlannerAreaAdmin(admin.ModelAdmin):
    inlines = (PlannerPlantingInline,)
    list_display = ("title", "planner", "area_type", "diary", "width_m", "height_m", "updated")
    list_filter = ("area_type", "created")
    search_fields = ("title", "planner__title", "planner__user__email", "diary__title")
    autocomplete_fields = ("planner", "diary")


@admin.register(PlannerPlanting)
class PlannerPlantingAdmin(admin.ModelAdmin):
    list_display = ("plant", "area", "mode", "status", "layout_summary", "updated")
    list_filter = ("mode", "status", "created")
    search_fields = ("plant__title", "plant__variety", "area__title", "area__planner__user__email")
    autocomplete_fields = ("area", "plant")


@admin.register(PlannerTask)
class PlannerTaskAdmin(admin.ModelAdmin):
    list_display = ("title", "planner", "area", "due_date", "is_completed", "updated")
    list_filter = ("is_completed", "due_date", "created")
    search_fields = ("title", "planner__title", "planner__user__email", "area__title")
    autocomplete_fields = ("planner", "area")


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
