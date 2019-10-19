from __future__ import unicode_literals

from api.v1.services.views import CategoryReviewsViewSet

from rest_framework.routers import DefaultRouter

urlpatterns = []

router = DefaultRouter()
router.register('category/reviews', CategoryReviewsViewSet, 'category-reviews')

urlpatterns += router.urls
