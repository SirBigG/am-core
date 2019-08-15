from django.contrib import admin

from .models import Event, EventType
from .forms import EventForm


class EventTypeAdmin(admin.ModelAdmin):
    readonly_fields = ('slug',)


class EventAdmin(admin.ModelAdmin):
    form = EventForm
    readonly_fields = ('slug',)
    list_display = ['title', 'start', 'stop', 'status']


admin.site.register(Event, EventAdmin)
admin.site.register(EventType, EventTypeAdmin)
