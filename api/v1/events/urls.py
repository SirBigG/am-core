from django.urls import path

from rest_framework.urlpatterns import format_suffix_patterns

from .views import EventTypeListView, EventCreateView


urlpatterns = format_suffix_patterns([
    path('event_types/', EventTypeListView.as_view(), name='event-types-list'),
    path('event/create/', EventCreateView.as_view(), name='event-create'),
])
