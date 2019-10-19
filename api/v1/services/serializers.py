from core.services.models import Reviews

from rest_framework import serializers


class ReviewsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reviews
        fields = ('pk', 'mark', 'description')
