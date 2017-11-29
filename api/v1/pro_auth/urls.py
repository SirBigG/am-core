from __future__ import unicode_literals

from api.v1.pro_auth.views import UserViewSet

from .routers import ProfileRouter

urlpatterns = []

router = ProfileRouter()
router.register('users', UserViewSet)

urlpatterns += router.urls
