from django.urls import path

from . import views


app_name = 'adverts'


urlpatterns = [
    path('', views.AdvertListView.as_view(), name="list"),
    path('create/', views.AdvertFormView.as_view(), name='adverts-create'),
]
