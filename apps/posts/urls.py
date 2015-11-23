from django.conf.urls import include, url
from . import views
from views import ListPostView, PostView

urlpatterns = [
    url(r'^$', ListPostView.as_view(), name='list_post_view'),
    url(r'^(?P<page>\d+)/$', ListPostView.as_view(), name='list_post_view'),
    url(r'^(?P<slug>\w+)/(?P<pk>\d+)/$', PostView.as_view(), name='post_view'),
#TODO: view posts with category things  /<category>/<pk>/ and /posts/<category>/ not /posts/
]