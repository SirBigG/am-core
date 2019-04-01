from __future__ import unicode_literals

from django.conf.urls import url

from core.classifier.views import LocationAutocomplete, TagAutocomplete


urlpatterns = [
    url(r'^location-autocomplete/$', LocationAutocomplete.as_view(),
        name='location-autocomplete'),
    url(r'^taggit-autocomplete/$', TagAutocomplete.as_view(), name='taggit-autocomplete'),
]
