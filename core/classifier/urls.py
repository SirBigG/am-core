from django.urls import path

from core.classifier.views import DiaryPlantCategoryAutocomplete, LocationAutocomplete, TagAutocomplete

urlpatterns = [
    path("location-autocomplete/", LocationAutocomplete.as_view(), name="location-autocomplete"),
    path("taggit-autocomplete/", TagAutocomplete.as_view(), name="taggit-autocomplete"),
    path(
        "diary-plant-category-autocomplete/",
        DiaryPlantCategoryAutocomplete.as_view(),
        name="diary-plant-category-autocomplete",
    ),
]
