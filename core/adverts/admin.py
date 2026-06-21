from django.contrib import admin

from .models import (
    Advert,
    AdvertImage,
)


class AdvertImageInline(admin.TabularInline):
    model = AdvertImage
    extra = 1


@admin.register(Advert)
class AdvertAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "author", "views", "category", "location", "price", "updated", "created")
    raw_id_fields = ("user", "category", "location")
    inlines = (AdvertImageInline,)
