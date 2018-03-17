from rest_framework.generics import ListAPIView, CreateAPIView
from rest_framework.permissions import IsAuthenticated

from core.events.models import EventType

from .serializers import EventTypeSerializer, EventSerializer


class EventTypeListView(ListAPIView):
    serializer_class = EventTypeSerializer
    queryset = EventType.objects.all().order_by('title')


class EventCreateView(CreateAPIView):
    serializer_class = EventSerializer
    permission_classes = (IsAuthenticated,)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
