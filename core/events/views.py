from datetime import datetime

from django.views.generic import ListView, DetailView

from .models import Event


class EventList(ListView):
    """
    View for list of posts by category.
    """
    paginate_by = 20
    template_name = 'events/list.html'
    ordering = '-start'

    def get_queryset(self):
        return Event.objects.filter(status=1, start__gte=datetime.now())


class EventDetail(DetailView):
    """
    Return one post from list.
    """
    model = Event
    template_name = 'events/detail.html'
