from django.conf.urls import include, url
from . import views
from views import ListPostView, PostDisplay

urlpatterns = [
    url(r'^$', ListPostView.as_view(), name='list_post_view'),
    url(r'^(?P<page>\d+)/$', ListPostView.as_view(), name='list_post_view'),
    url(r'^(?P<slug>\w+)/(?P<pk>\d+)/$', PostDisplay.as_view(), name='post_view'),
#TODO: view posts with category things  /<category>/<pk>/ and /posts/<category>/ not /posts/
]