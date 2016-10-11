from __future__ import unicode_literals

from django.conf.urls import url

from core.classifier.views import LocationAutocomplete


urlpatterns = [
    url(r'^location-autocomplete/$', LocationAutocomplete.as_view(),
        name='location-autocomplete'),
]
