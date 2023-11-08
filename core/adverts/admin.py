from django.contrib import admin

from .models import (
    Advert,
)


@admin.register(Advert)
class AdvertAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "author", "category", "location", "price", "updated", "created")
    raw_id_fields = ("user", "category", "location")
