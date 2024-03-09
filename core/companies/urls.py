from django.urls import path

from .views import CompanyListView, CompanyDetailView

app_name = 'companies'

urlpatterns = [
    path('', CompanyListView.as_view(), name='list'),
    path('<str:slug>-<int:pk>.html', CompanyDetailView.as_view(), name='detail'),
]
