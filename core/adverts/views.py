from django.conf import settings
from django.http.response import Http404, HttpResponseGone, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, TemplateView, UpdateView, View

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


class ProfileAdvertListView(ListView):
    template_name = "adverts/profile/list.html"
    model = Advert
    ordering = "-updated"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user).prefetch_related("photos")


class ProfileAdvertAddView(FormView):
    form_class = AdvertForm
    template_name = "adverts/profile/add.html"

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.save()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class UpdateProfileAdvertsView(UpdateView):
    form_class = AdvertForm
    template_name = "adverts/profile/update.html"

    def get_queryset(self):
        return Advert.objects.filter(user=self.request.user).prefetch_related("photos")

    def get_success_url(self):
        return reverse("pro_auth:profile-adverts")

    def form_valid(self, form):
        self.object = form.save()
        return HttpResponseRedirect(self.get_success_url())


class UpdateProfileAdvertsDateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.updated = timezone.now()
        advert.save()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertDeleteView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.delete()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertDeactivateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.deactivate()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertActivateView(View):
    def get(self, request, pk):
        advert = get_object_or_404(Advert, pk=pk, user=request.user)
        advert.activate()
        return HttpResponseRedirect(reverse("pro_auth:profile-adverts"))


class AdvertListView(ListView):
    paginate_by = 25
    template_name = "adverts/list.html"
    queryset = Advert.active_objects.prefetch_related("photos")
    ordering = "-updated"

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            return HttpResponseGone()


class AdvertDetailView(DetailView):
    model = Advert
    template_name = "adverts/detail.html"
    queryset = Advert.objects.prefetch_related("photos")

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
