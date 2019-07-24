from datetime import datetime

from django.views.generic import ListView, DetailView, FormView

from .models import Event
from .forms import EventAddForm


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


class EventFormView(FormView):
    form_class = EventAddForm
    template_name = "events/form.html"
    success_url = "/events/"

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
