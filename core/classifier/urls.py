from django.urls import path

from core.classifier.views import LocationAutocomplete, TagAutocomplete


urlpatterns = [
    path('location-autocomplete/', LocationAutocomplete.as_view(),
        name='location-autocomplete'),
    path('taggit-autocomplete/', TagAutocomplete.as_view(), name='taggit-autocomplete'),
]
