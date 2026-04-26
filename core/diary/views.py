from dal import autocomplete
from django.db.models import Prefetch, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, UpdateView, View

from .forms import DiaryForm, DiaryItemForm, PlantAttachmentFormSet, save_diary_plants
from .models import Diary, DiaryItem, Plant
from .recommendations import PlantRecommendationService


class DiaryListView(ListView):
    template_name = "diary/list.html"
    model = Diary
    paginate_by = 50
    ordering = "-updated"

    def get_queryset(self):
        return Diary.objects.filter(public=True).prefetch_related("plants__category").order_by("-updated")


class DiaryDetailView(DetailView):
    model = Diary
    template_name = "diary/detail.html"

    def get_queryset(self):
        return Diary.objects.filter(id=self.kwargs["pk"]).prefetch_related("plants__category")


class PlantAutocomplete(autocomplete.Select2QuerySetView):
    """Return current user's active plants."""

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Plant.objects.none()

        qs = Plant.objects.filter(
            user=self.request.user,
            status="active",
        ).select_related("category")

        if self.q:
            qs = qs.filter(
                Q(title__icontains=self.q) | Q(variety__icontains=self.q) | Q(category__value__icontains=self.q)
            )

        return qs


class DiaryPlantFormSetMixin:
    plant_formset_class = PlantAttachmentFormSet

    def get_plant_formset_initial(self):
        return []

    def get_plant_formset(self):
        kwargs = {
            "prefix": "plants",
            "request": self.request,
        }
        if self.request.method in ("POST", "PUT"):
            kwargs["data"] = self.request.POST
        else:
            kwargs["initial"] = self.get_plant_formset_initial()
        return self.plant_formset_class(**kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plant_formset"] = getattr(self, "plant_formset", None) or self.get_plant_formset()
        return context

    def form_invalid(self, form):
        if not hasattr(self, "plant_formset"):
            self.plant_formset = self.get_plant_formset()
        return super().form_invalid(form)


class AddDiaryView(DiaryPlantFormSetMixin, FormView):
    form_class = DiaryForm
    template_name = "diary/profile/add_diary.html"

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def form_valid(self, form):
        self.plant_formset = self.get_plant_formset()
        if not self.plant_formset.is_valid():
            return self.form_invalid(form)

        form.save()
        save_diary_plants(form.instance, self.request.user, self.plant_formset)
        return HttpResponseRedirect(form.instance.get_profile_absolute_url())


class ProfileDiaryListView(ListView):
    template_name = "diary/profile/diary_list.html"
    model = Diary
    ordering = "-updated"

    def get_queryset(self):
        return (
            Diary.objects.filter(user=self.request.user)
            .prefetch_related(
                "plants__category",
                Prefetch(
                    "plants",
                    queryset=Plant.objects.filter(status="active").select_related("category"),
                    to_attr="active_diary_plants",
                ),
                Prefetch(
                    "diary_items",
                    queryset=DiaryItem.objects.prefetch_related("plants__category"),
                    to_attr="latest_diary_items",
                ),
            )
            .order_by("-updated")
        )


class ProfileDiaryDetailView(DetailView):
    model = Diary
    template_name = "diary/profile/diary_detail.html"
    recommendation_service = PlantRecommendationService()

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user).prefetch_related(
            "plants__category",
            Prefetch("diary_items", queryset=DiaryItem.objects.prefetch_related("plants__category")),
        )

    def get_filtered_diary_items(self):
        plant_id = self.request.GET.get("plant")
        search_query = self.request.GET.get("q", "").strip()
        diary_items = self.object.diary_items.all()

        if plant_id:
            diary_items = diary_items.filter(plants__id=plant_id)

        if search_query:
            diary_items = diary_items.filter(
                Q(description__icontains=search_query) | Q(action_type__icontains=search_query)
            )

        return list(diary_items.distinct())

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary_items = self.get_filtered_diary_items()
        latest_item = diary_items[0] if diary_items else None

        context["diary_items"] = diary_items
        context["diary_plants"] = self.object.plants.all()
        context["selected_plant_id"] = self.request.GET.get("plant", "")
        context["event_search_query"] = self.request.GET.get("q", "").strip()
        context["recommendation"] = None

        if latest_item:
            fallback_recommendation = self.recommendation_service.generate(
                plant_name=self.object.plant_summary,
                plant_date=self.object.plant_date,
                action_type=latest_item.action_type,
                note=latest_item.description,
                last_actions=[
                    {
                        "action_type": item.action_type,
                        "date": item.date.isoformat(),
                        "has_photo": bool(item.image),
                    }
                    for item in diary_items[:5]
                ],
                has_photo=bool(latest_item.image),
                use_ai=False,
            )
            context["recommendation"] = self.recommendation_service.build_cached_recommendation(
                self.request,
                diary_id=self.object.id,
                item_id=latest_item.id,
                fallback_recommendation=fallback_recommendation,
            )

        return context


class UpdateProfileDiaryView(DiaryPlantFormSetMixin, UpdateView):
    form_class = DiaryForm
    template_name = "diary/profile/diary_update.html"

    def get_plant_formset_initial(self):
        return [
            {
                "existing_plant": plant.pk,
            }
            for plant in self.get_object().plants.filter(status="active")
        ]

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user)

    def get_success_url(self):
        return self.get_object().get_profile_absolute_url()

    def form_valid(self, form):
        self.plant_formset = self.get_plant_formset()
        if not self.plant_formset.is_valid():
            return self.form_invalid(form)

        form.save()
        save_diary_plants(form.instance, self.request.user, self.plant_formset)
        form.instance.save(update_fields=["updated"])
        return super().form_valid(form)


class AddDiaryItemView(FormView):
    form_class = DiaryItemForm
    template_name = "diary/profile/diary_item_form.html"
    recommendation_service = PlantRecommendationService()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["diary"] = get_object_or_404(Diary, pk=self.kwargs["diary_id"], user=self.request.user)
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["diary"] = get_object_or_404(Diary, pk=self.kwargs["diary_id"], user=self.request.user)
        return kwargs

    def form_valid(self, form):
        form.save()
        diary = form.instance.diary
        diary_items = list(diary.diary_items.all())

        recommendation = self.recommendation_service.generate(
            plant_name=diary.plant_summary,
            plant_date=diary.plant_date,
            action_type=form.instance.action_type,
            note=form.instance.description,
            last_actions=[
                {
                    "action_type": item.action_type,
                    "date": item.date.isoformat(),
                    "has_photo": bool(item.image),
                }
                for item in diary_items[:5]
            ],
            has_photo=bool(form.instance.image),
            use_ai=True,
        )
        self.recommendation_service.cache_recommendation(
            self.request,
            diary_id=diary.id,
            item_id=form.instance.id,
            recommendation=recommendation,
        )
        diary.save(update_fields=["updated"])
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.kwargs["diary_id"]}))


class UpdateDiaryItemView(UpdateView):
    form_class = DiaryItemForm
    template_name = "diary/profile/diary_item_form.html"
    recommendation_service = PlantRecommendationService()

    def get_queryset(self):
        return DiaryItem.objects.filter(diary__user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["diary"] = self.object.diary
        context["is_edit_mode"] = True
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["diary"] = self.get_object().diary
        return kwargs

    def form_valid(self, form):
        form.save()
        self.object.diary.updated = timezone.now()
        self.object.diary.save(update_fields=["updated"])
        self.recommendation_service.clear_cached_recommendation(self.request, diary_id=self.object.diary_id)
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.object.diary_id}))


class DiaryDeleteView(View):
    recommendation_service = PlantRecommendationService()

    def get(self, request, pk):
        diary = get_object_or_404(Diary, pk=pk, user=request.user)
        self.recommendation_service.clear_cached_recommendation(request, diary_id=diary.id)
        diary.delete()
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-list"))


class DiaryItemDeleteView(View):
    recommendation_service = PlantRecommendationService()

    def get(self, request, pk):
        diary_item = get_object_or_404(DiaryItem, pk=pk, diary__user=request.user)
        diary_pk = diary_item.diary_id
        diary = diary_item.diary
        self.recommendation_service.clear_cached_recommendation(request, diary_id=diary_pk)
        diary_item.delete()
        diary.save(update_fields=["updated"])
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": diary_pk}))
