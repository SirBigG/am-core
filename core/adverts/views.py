from django.conf import settings
from django.http.response import Http404, HttpResponseGone, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import DetailView, FormView, ListView, TemplateView

from .forms import AdvertForm
from .models import Advert


class AdvertFormView(FormView):
    form_class = AdvertForm
    template_name = "adverts/form.html"

    def form_valid(self, form):
        if self.request.user.is_authenticated:
            form.instance.user = self.request.user
        form.save()
        return HttpResponseRedirect(reverse("adverts:list"))


class AdvertListView(ListView):
    paginate_by = 25
    template_name = "adverts/list.html"
    queryset = Advert.active_objects.all()
    ordering = "-updated"

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            return HttpResponseGone()


class AdvertDetailView(DetailView):
    model = Advert
    template_name = "adverts/detail.html"

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # increment views count
        obj.views += 1
        obj.save(update_fields=["views"])
        return obj


class AdvertSitemap(TemplateView):
    template_name = "sitemap.xml"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["urls"] = [
            {
                "loc": f"{settings.HOST}{reverse('adverts:detail', kwargs={'pk': i['pk'], 'slug': i['slug']})}",
                "lastmod": i["updated"],
            }
            for i in Advert.active_objects.values("updated", "slug", "pk")
        ]
        return context
