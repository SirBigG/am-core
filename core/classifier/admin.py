from __future__ import unicode_literals

from django.contrib import admin

from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Location, Country, Region, Area, \
    Category


class CategoryAdmin(DraggableMPTTAdmin, admin.ModelAdmin):
    pass


admin.site.register(Location)
admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
admin.site.register(Category, CategoryAdmin)
