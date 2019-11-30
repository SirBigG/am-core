from datetime import date

from django.views.generic import ListView, DetailView, FormView

from .models import Event
from .forms import EventAddForm


class EventList(ListView):
    """
    View for list of posts by category.
    """
    paginate_by = 20
    template_name = 'events/list.html'
    ordering = 'start'
    queryset = Event.objects.filter(status=1, stop__gte=date.today())


class EventDetail(DetailView):
    """
    Return one post from list.
    """
    model = Event
    template_name = 'events/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ended"] = False if self.object.stop.date() >= date.today() else True
        return context


class EventFormView(FormView):
    form_class = EventAddForm
    template_name = "events/form.html"
    success_url = "/events/"

    def form_valid(self, form):
        form.save()
        return super().form_valid(form)
