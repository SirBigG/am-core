from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.EventList.as_view(), name='event-list'),
    path('create/', views.EventFormView.as_view(), name='event-form'),
    path('<str:slug>.html', views.EventDetail.as_view(), name='event-detail'),
]
