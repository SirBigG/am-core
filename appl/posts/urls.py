from django.conf.urls import url

from appl.posts.views import PostList, PostDetail, ApiPostList, RandomApiPostList, UserPostsViewSet

from rest_framework.routers import DefaultRouter


urlpatterns = [
    url(r'^api/post/all/$', ApiPostList.as_view(), name='api-post-list'),
    url(r'^api/post/random/all/$', RandomApiPostList.as_view(), name='api-post-random-list'),
]


router = DefaultRouter()
router.register('posts/user', UserPostsViewSet, 'Post')

urlpatterns += router.urls

urlpatterns += [
    url(r'^(?P<parent>[\w-]+)/$', PostList.as_view(), name='posts-list'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/$', PostList.as_view(), name='posts-list-child'),
    url(r'^(?P<parent>[\w-]+)/(?P<child>[\w-]+)/(?P<slug>[\w-]+)-(?P<id>[\w-]+).html$',
        PostDetail.as_view(), name='post-detail'),
]
