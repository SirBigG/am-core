from django.conf.urls import url

from rest_framework.urlpatterns import format_suffix_patterns

from .views import EventTypeListView, EventCreateView


urlpatterns = format_suffix_patterns([
    url(r'event_types/$', EventTypeListView.as_view(), name='event-types-list'),
    url(r'event/create/$', EventCreateView.as_view(), name='event-create'),
])
