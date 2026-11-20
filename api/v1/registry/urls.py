from django.urls import path

from .views import AddActiveVarietyView, AddCompanyView, AddInactiveVarietyView, VarietyPublicationView

urlpatterns = [
    path(
        "varieties/<int:variety_id>/publication/", VarietyPublicationView.as_view(), name="registry-variety-publication"
    ),
    path("add-company/", AddCompanyView.as_view()),
    path("add-active-variety/", AddActiveVarietyView.as_view()),
    path("add-inactive-variety/", AddInactiveVarietyView.as_view()),
]
