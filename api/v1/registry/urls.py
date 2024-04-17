from django.urls import path

from .views import AddActiveVarietyView, AddCompanyView, AddInactiveVarietyView

urlpatterns = [
    path("add-company/", AddCompanyView.as_view()),
    path("add-active-variety/", AddActiveVarietyView.as_view()),
    path("add-inactive-variety/", AddInactiveVarietyView.as_view()),
]
