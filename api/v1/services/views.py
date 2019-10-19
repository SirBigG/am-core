from rest_framework.viewsets import ModelViewSet

from api.v1.services.serializers import ReviewsSerializer
from api.v1.services.permissions import CreateUpdatePermission

from core.classifier.models import Category

from django.contrib.contenttypes.models import ContentType


class CategoryReviewsViewSet(ModelViewSet):
    serializer_class = ReviewsSerializer
    permission_classes = [CreateUpdatePermission, ]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, content_type=ContentType.objects.get(model='category'),
                        object_id=Category.objects.get(slug=self.request.data.get('slug')).pk)
