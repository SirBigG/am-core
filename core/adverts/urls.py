from django.urls import path

from . import views


app_name = 'adverts'


urlpatterns = [
    path('', views.AdvertListView.as_view(), name="list"),
    path('<str:category>/', views.AdvertListView.as_view(), name="adverts-list-categories"),
    path('create/', views.AdvertFormView.as_view(), name='adverts-create'),
]
