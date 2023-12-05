from django.urls import path

from . import views


app_name = 'news'


urlpatterns = [
    path('', views.NewsListView.as_view(), name='news-list'),
    path('<str:slug>-<int:pk>.html', views.NewsDetailView.as_view(), name='news-detail'),
]
