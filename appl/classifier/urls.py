# -*- coding: utf-8 -*-

from django.conf.urls import url

from appl.classifier.views import LocationAutocomplete


urlpatterns = [
    url(r'^location-autocomplete/$', LocationAutocomplete.as_view(),
        name='location-autocomplete'),
]
