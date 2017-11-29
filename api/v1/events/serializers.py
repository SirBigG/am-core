from rest_framework import serializers

from core.events.models import EventType, Event


class EventTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventType
        fields = ('pk', 'title',)


class EventSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField('get_absolute_url', read_only=True)

    class Meta:
        model = Event
        fields = ('title', 'address', 'text', 'start', 'stop', 'type', 'location', 'poster',)

    def get_absolute_url(self, instance):
        return instance.get_absolute_url()
