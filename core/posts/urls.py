from django.conf.urls import url

from core.posts.views import PostList, PostDetail


urlpatterns = [
    url(r'^(?P<parent>[\w-]+)/$', PostList.as_view(), name='posts-list'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/$', PostList.as_view(), name='posts-list-child'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/(?P<slug>[\w-]+)-(?P<id>[\w-]+).html$',
        PostDetail.as_view(), name='post-detail'),
]
