from django.urls import path

from . import views

app_name = "diary"


urlpatterns = [
    path('<int:pk>', views.DiaryDetailView.as_view(), name='detail'),
    path('', views.DiaryListView.as_view(), name='list'),
]
