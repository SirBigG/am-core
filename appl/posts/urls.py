from django.conf.urls import url
from django.views.decorators.cache import cache_page

from appl.posts.views import PostList, PostDetail, ApiPostList, RandomApiPostList


urlpatterns = [
    url(r'^api/post/all/$', ApiPostList.as_view(), name='api-post-list'),
    url(r'^api/post/random/all/$', RandomApiPostList.as_view(), name='api-post-random-list'),
    url(r'^(?P<parent>[\w-]+)/$', PostList.as_view(), name='posts-list'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/$', PostList.as_view(), name='posts-list-child'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/(?P<slug>[\w-]+)-(?P<id>[\w-]+).html$',
        cache_page(60 * 15, key_prefix='post_')(PostDetail.as_view()), name='post-detail'),
]
