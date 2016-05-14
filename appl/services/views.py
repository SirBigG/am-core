from django.views.generic import FormView
from django.http import HttpResponse
from django.template.loader import render_to_string

from appl.services.forms import FeedbackForm


class FeedbackView(FormView):
    form_class = FeedbackForm
    template_name = 'services/feedback.html'

    def form_valid(self, form):
        form.save()
        render = render_to_string('services/success.html')
        return HttpResponse(render)
