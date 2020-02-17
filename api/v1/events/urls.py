from django.urls import path

from rest_framework.urlpatterns import format_suffix_patterns

from .views import EventTypeListView, EventCreateView, EventListView


urlpatterns = format_suffix_patterns([
    path('event_types/', EventTypeListView.as_view(), name='event-types-list'),
    path('event/create/', EventCreateView.as_view(), name='event-create'),
    path('events/', EventListView.as_view(), name='event-list'),
])
