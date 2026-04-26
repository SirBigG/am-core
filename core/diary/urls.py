from django.urls import path

from . import views

app_name = "diary"


urlpatterns = [
    path("plant-autocomplete/", views.PlantAutocomplete.as_view(), name="plant-autocomplete"),
    path("<int:pk>", views.DiaryDetailView.as_view(), name="detail"),
    path("", views.DiaryListView.as_view(), name="list"),
]
