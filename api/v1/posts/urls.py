from django.conf.urls import url

from api.v1.posts.views import ApiPostList, RandomApiPostList, UserPostsViewSet

from rest_framework.routers import DefaultRouter


urlpatterns = [
    url(r'^post/all/$', ApiPostList.as_view(), name='api-post-list'),
    url(r'^post/random/all/$', RandomApiPostList.as_view(), name='api-post-random-list'),
]


router = DefaultRouter()
router.register('user/posts', UserPostsViewSet, 'Post')

urlpatterns += router.urls
