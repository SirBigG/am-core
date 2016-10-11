from rest_framework import serializers

from core.classifier.models import Location, Category


class LocationSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField('get_location_value')

    class Meta:
        model = Location
        fields = ('pk', 'value')

    def get_location_value(self, instance):
        return str(instance)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('pk', 'value')
