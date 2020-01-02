from django.urls import path

from api.v1.posts.views import ApiPostList, RandomApiPostList, UserPostsViewSet, PostView, PostUsefulView

from rest_framework.routers import DefaultRouter


urlpatterns = [
    path('post/all/', ApiPostList.as_view(), name='api-post-list'),
    path('post/random/all/', RandomApiPostList.as_view(), name='api-post-random-list'),
    path('post/view/', PostView.as_view(), name='api-post-view'),
    path('post/useful/', PostUsefulView.as_view(), name='api-post-useful'),
]


router = DefaultRouter()
router.register('user/posts', UserPostsViewSet, 'Post')

urlpatterns += router.urls
