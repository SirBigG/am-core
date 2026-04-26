from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Area, Category, Country, Location, Region


class CategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    list_display = ("tree_actions", "indented_title", "slug", "is_active", "is_diary_species_parent")
    list_filter = ("is_active", "is_diary_species_parent", "is_for_user")
    search_fields = ["value", "slug"]


class LocationAdmin(admin.ModelAdmin):
    list_display = ("value", "longitude", "latitude", "region", "area")
    list_filter = ("region", "area")
    search_fields = ("value",)


admin.site.register(Location, LocationAdmin)
admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
admin.site.register(Category, CategoryAdmin)
