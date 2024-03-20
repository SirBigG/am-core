from django.contrib import admin
from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Area, Category, Country, Location, Region


class CategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    pass


class LocationAdmin(admin.ModelAdmin):
    list_display = ("value", "longitude", "latitude", "region", "area")
    list_filter = ("region", "area")
    search_fields = ("value",)


admin.site.register(Location, LocationAdmin)
admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
admin.site.register(Category, CategoryAdmin)
