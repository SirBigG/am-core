from django.views.generic import FormView, ListView
from django.http.response import HttpResponseRedirect
from django.urls import reverse

from .forms import AdvertForm
from .models import Advert


class AdvertFormView(FormView):
    form_class = AdvertForm
    template_name = "adverts/form.html"

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse("adverts:list"))


class AdvertListView(ListView):
    paginate_by = 25
    template_name = "adverts/list.html"
    queryset = Advert.objects.all()
    ordering = "-created"
