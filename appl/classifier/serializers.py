from rest_framework import serializers

from appl.classifier.models import Location


class LocationSerializer(serializers.ModelSerializer):
    value = serializers.SerializerMethodField('get_location_value')

    class Meta:
        model = Location
        fields = ('pk', 'value')

    def get_location_value(self, instance):
        return str(instance)
