from __future__ import unicode_literals

from api.v1.services.views import PostCommentsViewSet

from rest_framework.routers import DefaultRouter

urlpatterns = []

router = DefaultRouter()
router.register('post/comments', PostCommentsViewSet, 'post-comments')

urlpatterns += router.urls
