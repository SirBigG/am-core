from __future__ import unicode_literals

from django.contrib import admin

from mptt.admin import DraggableMPTTAdmin

from core.classifier.models import Location, Country, Region, Area, \
    Category

from modeltranslation.admin import TranslationAdmin


class CategoryAdmin(DraggableMPTTAdmin, TranslationAdmin):
    pass


admin.site.register(Location, TranslationAdmin)
admin.site.register(Country, TranslationAdmin)
admin.site.register(Region, TranslationAdmin)
admin.site.register(Area, TranslationAdmin)
admin.site.register(Category, CategoryAdmin)
