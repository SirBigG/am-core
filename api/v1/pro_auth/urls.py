from __future__ import unicode_literals

from api.v1.pro_auth.views import UserViewSet

from rest_framework.routers import DefaultRouter

urlpatterns = []

router = DefaultRouter()
router.register('users', UserViewSet)

urlpatterns += router.urls
