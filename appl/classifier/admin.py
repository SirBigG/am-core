# -*- coding: utf-8 -*-

from django.contrib import admin

from appl.classifier.models import Location, Country, Region, Area

admin.site.register(Location)
admin.site.register(Country)
admin.site.register(Region)
admin.site.register(Area)
