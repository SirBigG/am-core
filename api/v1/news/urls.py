from django.conf.urls import url

from rest_framework.urlpatterns import format_suffix_patterns

from .views import CreateNewsView


urlpatterns = format_suffix_patterns([
    url(r'news/$', CreateNewsView.as_view(), name='news-create'),
])
