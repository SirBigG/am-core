import re
from collections import OrderedDict
from datetime import date

from dal import autocomplete
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils import timezone
from django.views.generic import DetailView, FormView, ListView, UpdateView, View

from .forms import DiaryForm, DiaryItemForm, PlantAttachmentFormSet, PlantMoveForm, PlantingForm, save_diary_plants
from .models import DIARY_ITEM_ACTION_CHOICES, Diary, DiaryItem, Plant
from .recommendations import PlantRecommendationService

TRANSPLANTED_TO_PREFIX = "Рослину пересаджено до щоденника: "
TRANSPLANTED_FROM_PREFIX = "Рослину пересаджено з щоденника: "

PLANT_ARCHIVE_TITLE = "Архівувати рослину"
PLANT_ARCHIVE_LEAD = "Рослина зникне зі списку тих, що ростуть зараз, але її історія збережеться в архіві. Ви зможете переглядати всі записи та відновити рослину пізніше."
PLANT_RESTORE_TITLE = "Відновити рослину з архіву"
PLANT_RESTORE_LEAD = "Рослина знову з’явиться серед тих, що ростуть, і для неї можна буде додавати нові дії."
PLANT_DELETE_TITLE = "Видалити рослину назавжди"
PLANT_DELETE_LEAD = "Рослина буде повністю видалена разом з її історією, діями та пов’язаними записами. Цю дію не можна скасувати."


def _build_recommendation_target(item, *, selected_plant_id=None):
    target_plants = list(item.plants.all())
    selected_plant = None
    if selected_plant_id:
        selected_plant = next((plant for plant in target_plants if str(plant.id) == str(selected_plant_id)), None)

    if selected_plant is not None:
        return {
            "label": selected_plant.display_name,
            "plant_name": selected_plant.display_name,
            "plant_date": selected_plant.plant_date,
        }

    if item.apply_to_all:
        return {
            "label": "усіх активних рослин",
            "plant_name": "усіх активних рослин",
            "plant_date": None,
        }

    if len(target_plants) == 1:
        plant = target_plants[0]
        return {
            "label": plant.display_name,
            "plant_name": plant.display_name,
            "plant_date": plant.plant_date,
        }

    if len(target_plants) <= 2:
        label = ", ".join(plant.display_name for plant in target_plants)
        return {
            "label": label,
            "plant_name": label,
            "plant_date": None,
        }

    return {
        "label": f"{len(target_plants)} рослин",
        "plant_name": ", ".join(plant.display_name for plant in target_plants[:3]),
        "plant_date": None,
    }


def _build_diary_filter_plants(diary):
    current_plants = {plant.pk: plant for plant in diary.plants.all()}
    historical_plants = {}

    for item in diary.diary_items.all():
        for plant in item.plants.all():
            if plant.pk not in current_plants:
                historical_plants[plant.pk] = plant

    combined = [
        {
            "plant": plant,
            "filter_label": f"{plant.display_name} (в архіві)" if plant.status == "completed" else plant.display_name,
            "is_historical": False,
        }
        for plant in current_plants.values()
    ]
    combined.extend(
        {
            "plant": plant,
            "filter_label": f"{plant.display_name} (перенесена)",
            "is_historical": True,
        }
        for plant in historical_plants.values()
    )
    return sorted(
        combined,
        key=lambda item: (
            item["is_historical"],
            item["plant"].status == "completed",
            item["plant"].display_name.lower(),
        ),
    )


class DiaryListView(ListView):
    template_name = "diary/list.html"
    model = Diary
    paginate_by = 50
    ordering = "-updated"

    def get_queryset(self):
        return Diary.objects.filter(public=True, is_archived=False).prefetch_related("plants__category").order_by(
            "-updated"
        )


class DiaryDetailView(DetailView):
    model = Diary
    template_name = "diary/detail.html"

    def get_queryset(self):
        return Diary.objects.filter(id=self.kwargs["pk"], public=True, is_archived=False).prefetch_related(
            "plants__category"
        )


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

    def get_plant_formset_kwargs(self):
        return {}

    def get_plant_formset(self):
        kwargs = {
            "prefix": "plants",
            "request": self.request,
        }
        kwargs.update(self.get_plant_formset_kwargs())
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
        try:
            save_diary_plants(form.instance, self.request.user, self.plant_formset)
        except ValidationError as error:
            self.plant_formset._non_form_errors = self.plant_formset.error_class(error.messages)
            return self.form_invalid(form)
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
                    "plants",
                    queryset=Plant.objects.filter(status="completed").select_related("category"),
                    to_attr="completed_diary_plants",
                ),
                Prefetch(
                    "diary_items",
                    queryset=DiaryItem.objects.prefetch_related("plants__category"),
                    to_attr="latest_diary_items",
                ),
            )
            .order_by("-updated")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diaries = list(context["object_list"])
        context["active_diaries"] = [diary for diary in diaries if not diary.is_archived]
        context["archived_diaries"] = [diary for diary in diaries if diary.is_archived]
        return context


class ProfileDiaryDetailView(DetailView):
    model = Diary
    template_name = "diary/profile/diary_detail.html"
    recommendation_service = PlantRecommendationService()

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user).prefetch_related(
            "plants__category",
            Prefetch("diary_items", queryset=DiaryItem.objects.prefetch_related("plants__category")),
        )

    def get_valid_selected_period(self):
        period = self.request.GET.get("period", "").strip()
        if not re.fullmatch(r"\d{4}-\d{2}", period):
            return ""
        year, month = period.split("-")
        if not 1 <= int(month) <= 12:
            return ""
        return f"{year}-{month}"

    def get_filtered_diary_items(self):
        plant_id = self.request.GET.get("plant")
        action_type = self.request.GET.get("action", "").strip()
        period = self.get_valid_selected_period()
        search_query = self.request.GET.get("q", "").strip()
        diary_items = self.object.diary_items.all()

        if plant_id:
            diary_items = diary_items.filter(plants__id=plant_id)

        if action_type:
            diary_items = diary_items.filter(action_type=action_type)

        if period:
            year, month = period.split("-")
            diary_items = diary_items.filter(date__year=int(year), date__month=int(month))

        if search_query:
            diary_items = diary_items.filter(
                Q(description__icontains=search_query) | Q(action_type__icontains=search_query)
            )

        return list(diary_items.distinct())

    def get_period_filter_options(self):
        options = OrderedDict()
        for item in self.object.diary_items.all():
            value = item.date.strftime("%Y-%m")
            if value in options:
                continue
            month_date = date(item.date.year, item.date.month, 1)
            options[value] = date_format(month_date, "F Y").capitalize()
        return [("", "Всі дати"), *options.items()]

    def get_grouped_diary_items(self, diary_items):
        groups = []
        for item in diary_items:
            if not groups or groups[-1]["date"] != item.date:
                groups.append({"date": item.date, "items": []})
            groups[-1]["items"].append(item)
        return groups

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diary_items = self.get_filtered_diary_items()
        grouped_diary_items = self.get_grouped_diary_items(diary_items)
        latest_item = diary_items[0] if diary_items else None
        active_diary_plants = [plant for plant in self.object.plants.all() if plant.status == "active"]
        completed_diary_plants = [plant for plant in self.object.plants.all() if plant.status == "completed"]
        selected_plant_id = self.request.GET.get("plant", "")
        selected_period = self.request.GET.get("period", "").strip()
        diary_filter_plants = _build_diary_filter_plants(self.object)

        context["diary_items"] = diary_items
        context["grouped_diary_items"] = grouped_diary_items
        context["diary_plants"] = self.object.plants.all()
        context["diary_filter_plants"] = diary_filter_plants
        context["active_diary_plants"] = active_diary_plants
        context["completed_diary_plants"] = completed_diary_plants
        context["has_active_plants"] = bool(active_diary_plants)
        context["selected_plant_id"] = selected_plant_id
        selected_action_type = self.request.GET.get("action", "").strip()
        event_search_query = self.request.GET.get("q", "").strip()
        context["selected_action_type"] = selected_action_type
        context["selected_period"] = selected_period
        context["action_filter_options"] = [("", "Всі дії"), *DIARY_ITEM_ACTION_CHOICES]
        context["period_filter_options"] = self.get_period_filter_options()
        context["event_search_query"] = event_search_query
        context["has_active_filters"] = bool(selected_plant_id or selected_action_type or selected_period or event_search_query)
        context["recommendation"] = None
        context["recommendation_target_label"] = None

        if latest_item:
            recommendation_target = _build_recommendation_target(latest_item, selected_plant_id=selected_plant_id)
            fallback_recommendation = self.recommendation_service.generate(
                plant_name=recommendation_target["plant_name"],
                plant_date=recommendation_target["plant_date"],
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
            context["recommendation_target_label"] = recommendation_target["label"]

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

    def get_plant_formset_kwargs(self):
        return {
            "allow_empty": True,
            "diary": self.get_object(),
        }

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
        try:
            save_diary_plants(form.instance, self.request.user, self.plant_formset)
        except ValidationError as error:
            self.plant_formset._non_form_errors = self.plant_formset.error_class(error.messages)
            return self.form_invalid(form)
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
        recommendation_target = _build_recommendation_target(form.instance)

        recommendation = self.recommendation_service.generate(
            plant_name=recommendation_target["plant_name"],
            plant_date=recommendation_target["plant_date"],
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


class PlantingView(FormView):
    form_class = PlantingForm
    template_name = "diary/profile/planting_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.diary = get_object_or_404(Diary, pk=self.kwargs["diary_id"], user=request.user, is_archived=False)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["diary"] = self.diary
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["diary"] = self.diary
        return context

    def form_valid(self, form):
        form.save()
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))


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
        diary.is_archived = True
        diary.updated = timezone.now()
        diary.save(update_fields=["is_archived", "updated"])
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-list"))


class DiaryRestoreView(View):
    def get(self, request, pk):
        diary = get_object_or_404(Diary, pk=pk, user=request.user)
        diary.is_archived = False
        diary.updated = timezone.now()
        diary.save(update_fields=["is_archived", "updated"])
        return HttpResponseRedirect(reverse("pro_auth:profile-diary-list"))


class PlantMoveView(FormView):
    form_class = PlantMoveForm
    template_name = "diary/profile/plant_move_form.html"

    def dispatch(self, request, *args, **kwargs):
        self.source_diary = get_object_or_404(Diary, pk=self.kwargs["diary_pk"], user=request.user, is_archived=False)
        self.plant = get_object_or_404(
            Plant.objects.filter(status="active", diaries=self.source_diary).distinct(),
            pk=self.kwargs["plant_pk"],
            user=request.user,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        kwargs["source_diary"] = self.source_diary
        kwargs["plant"] = self.plant
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_diary"] = self.source_diary
        context["plant"] = self.plant
        return context

    def form_valid(self, form):
        target_diary = form.cleaned_data["target_diary"]
        today = timezone.localdate()

        with transaction.atomic():
            source_diary = Diary.objects.select_for_update().get(pk=self.source_diary.pk, user=self.request.user)
            target_diary = Diary.objects.select_for_update().get(
                pk=target_diary.pk,
                user=self.request.user,
                is_archived=False,
            )
            plant = Plant.objects.select_for_update().get(pk=self.plant.pk, user=self.request.user, status="active")

            if not source_diary.plants.filter(pk=plant.pk).exists():
                form.add_error(None, "Ця рослина вже не прив’язана до поточного щоденника.")
                return self.form_invalid(form)

            if target_diary.pk == source_diary.pk:
                form.add_error("target_diary", "Оберіть інший щоденник для перенесення.")
                return self.form_invalid(form)

            target_diary.plants.add(plant)
            source_diary.plants.remove(plant)
            source_item = DiaryItem.objects.create(
                diary=source_diary,
                action_type="transplanted",
                apply_to_all=False,
                date=today,
                description=f"Рослину пересаджено до щоденника: {target_diary.title}",
            )
            source_item.plants.set([plant])
            target_item = DiaryItem.objects.create(
                diary=target_diary,
                action_type="transplanted",
                apply_to_all=False,
                date=today,
                description=f"Рослину пересаджено з щоденника: {source_diary.title}",
            )
            target_item.plants.set([plant])
            source_diary.save(update_fields=["updated"])
            target_diary.save(update_fields=["updated"])

        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": source_diary.pk}))


class PlantActionView(View):
    template_name = "diary/profile/plant_action_confirm.html"
    recommendation_service = PlantRecommendationService()
    action = ""
    button_label = ""
    button_class = "btn-success"
    title = ""
    lead = ""

    def dispatch(self, request, *args, **kwargs):
        self.diary = get_object_or_404(Diary, pk=self.kwargs["diary_pk"], user=request.user, is_archived=False)
        self.plant = get_object_or_404(
            Plant.objects.filter(user=request.user, diaries=self.diary).distinct(),
            pk=self.kwargs["plant_pk"],
        )
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self):
        return {
            "diary": self.diary,
            "plant": self.plant,
            "action_title": self.title,
            "action_lead": self.lead,
            "action_button_label": self.button_label,
            "action_button_class": self.button_class,
        }

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name, self.get_context_data())

    def post(self, request, *args, **kwargs):
        return self.perform_action(request)

    def perform_action(self, request):
        raise NotImplementedError


class PlantArchiveView(PlantActionView):
    action = "archive"
    button_label = "Архівувати"
    button_class = "btn-success"
    title = PLANT_ARCHIVE_TITLE
    lead = PLANT_ARCHIVE_LEAD

    def get_context_data(self):
        context = super().get_context_data()
        context["action_lead"] = (
            f"Рослина <strong>{self.plant.display_name}</strong> зникне зі списку тих, що ростуть зараз, "
            "але її історія збережеться в архіві. Ви зможете переглядати всі записи та відновити рослину пізніше."
        )
        return context

    def perform_action(self, request):
        today = timezone.localdate()
        with transaction.atomic():
            diary = Diary.objects.select_for_update().get(pk=self.diary.pk, user=request.user, is_archived=False)
            plant = Plant.objects.select_for_update().get(pk=self.plant.pk, user=request.user)

            if plant.status != "active" or not diary.plants.filter(pk=plant.pk).exists():
                return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": diary.pk}))

            plant.status = "completed"
            plant.completed_at = today
            plant.save(update_fields=["status", "completed_at"])
            finished_item = DiaryItem.objects.create(
                diary=diary,
                action_type="finished",
                apply_to_all=False,
                date=today,
                description="",
            )
            finished_item.plants.set([plant])
            diary.updated = timezone.now()
            diary.save(update_fields=["updated"])
            self.recommendation_service.clear_cached_recommendation(request, diary_id=diary.pk)

        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))


class PlantRestoreView(PlantActionView):
    action = "restore"
    button_label = "Відновити"
    button_class = "btn-success"
    title = PLANT_RESTORE_TITLE
    lead = PLANT_RESTORE_LEAD

    def get_context_data(self):
        context = super().get_context_data()
        context["action_lead"] = (
            f"Рослина <strong>{self.plant.display_name}</strong> знову з’явиться серед тих, що ростуть, "
            "і для неї можна буде додавати нові дії."
        )
        return context

    def perform_action(self, request):
        with transaction.atomic():
            diary = Diary.objects.select_for_update().get(pk=self.diary.pk, user=request.user, is_archived=False)
            plant = Plant.objects.select_for_update().get(pk=self.plant.pk, user=request.user)

            if plant.status != "completed" or not diary.plants.filter(pk=plant.pk).exists():
                return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": diary.pk}))

            latest_finished_item = (
                DiaryItem.objects.select_for_update()
                .filter(diary=diary, action_type="finished", plants=plant)
                .order_by("-date", "-created")
                .first()
            )

            if latest_finished_item is not None:
                latest_remaining_finished = (
                    DiaryItem.objects.filter(action_type="finished", plants=plant)
                    .exclude(pk=latest_finished_item.pk)
                    .order_by("-date", "-created")
                    .first()
                )

                if latest_remaining_finished is not None:
                    plant.status = "completed"
                    plant.completed_at = latest_remaining_finished.date
                else:
                    plant.status = "active"
                    plant.completed_at = None
                plant.save(update_fields=["status", "completed_at"])
                latest_finished_item.delete()
            else:
                plant.status = "active"
                plant.completed_at = None
                plant.save(update_fields=["status", "completed_at"])

            diary.updated = timezone.now()
            diary.save(update_fields=["updated"])
            self.recommendation_service.clear_cached_recommendation(request, diary_id=diary.pk)

        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))


class PlantDeleteView(PlantActionView):
    action = "delete"
    button_label = "Видалити"
    button_class = "btn-danger"
    title = PLANT_DELETE_TITLE
    lead = PLANT_DELETE_LEAD

    def get_context_data(self):
        context = super().get_context_data()
        context["action_lead"] = (
            f"Рослина <strong>{self.plant.display_name}</strong> буде повністю видалена разом з її історією, "
            "діями та пов’язаними записами. Цю дію не можна скасувати."
        )
        return context

    def perform_action(self, request):
        with transaction.atomic():
            plant = Plant.objects.select_for_update().get(pk=self.plant.pk, user=request.user)
            related_diaries = list(Diary.objects.filter(plants=plant, user=request.user).distinct())
            related_items = list(
                DiaryItem.objects.filter(plants=plant, diary__user=request.user).distinct().prefetch_related("plants")
            )

            for item in related_items:
                target_count = item.plants.count()
                if target_count <= 1:
                    item.delete()
                    continue
                item.plants.remove(plant)

            for diary in related_diaries:
                diary.updated = timezone.now()
                diary.save(update_fields=["updated"])
                self.recommendation_service.clear_cached_recommendation(request, diary_id=diary.pk)

            plant.delete()

        return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": self.diary.pk}))


class DiaryItemDeleteView(View):
    recommendation_service = PlantRecommendationService()

    def _restore_plant_statuses_for_finished_item(self, diary_item):
        if diary_item.action_type != "finished":
            return

        affected_plants = list(diary_item.plants.all())
        for plant in affected_plants:
            latest_remaining_finished = (
                DiaryItem.objects.filter(action_type="finished", plants=plant)
                .exclude(pk=diary_item.pk)
                .order_by("-date", "-created")
                .first()
            )

            if latest_remaining_finished is not None:
                if plant.status != "completed" or plant.completed_at != latest_remaining_finished.date:
                    plant.status = "completed"
                    plant.completed_at = latest_remaining_finished.date
                    plant.save(update_fields=["status", "completed_at"])
                continue

            if plant.status == "completed" and plant.completed_at == diary_item.date:
                plant.status = "active"
                plant.completed_at = None
                plant.save(update_fields=["status", "completed_at"])

    def _find_transplanted_counterpart(self, diary_item, plant):
        candidates = (
            DiaryItem.objects.filter(action_type="transplanted", date=diary_item.date, plants=plant)
            .exclude(pk=diary_item.pk)
            .exclude(diary=diary_item.diary)
            .select_related("diary")
            .order_by("-created")
        )

        if diary_item.description.startswith(TRANSPLANTED_TO_PREFIX):
            expected_description = f"{TRANSPLANTED_FROM_PREFIX}{diary_item.diary.title}"
            return candidates.filter(description=expected_description).first() or candidates.first()

        if diary_item.description.startswith(TRANSPLANTED_FROM_PREFIX):
            expected_description = f"{TRANSPLANTED_TO_PREFIX}{diary_item.diary.title}"
            return candidates.filter(description=expected_description).first() or candidates.first()

        return candidates.first()

    def _undo_transplanted_item(self, request, diary_item):
        if diary_item.action_type != "transplanted":
            return False, None

        plants = list(diary_item.plants.all())
        if len(plants) != 1:
            return False, None

        plant = plants[0]
        counterpart = self._find_transplanted_counterpart(diary_item, plant)
        if counterpart is None:
            return False, None

        if diary_item.description.startswith(TRANSPLANTED_TO_PREFIX):
            source_diary = diary_item.diary
            target_diary = counterpart.diary
        elif diary_item.description.startswith(TRANSPLANTED_FROM_PREFIX):
            source_diary = counterpart.diary
            target_diary = diary_item.diary
        else:
            return False, None

        source_diary = Diary.objects.select_for_update().get(pk=source_diary.pk, user=request.user)
        target_diary = Diary.objects.select_for_update().get(pk=target_diary.pk, user=request.user)
        plant = Plant.objects.select_for_update().get(pk=plant.pk, user=request.user)

        if target_diary.plants.filter(pk=plant.pk).exists():
            source_diary.plants.add(plant)
            target_diary.plants.remove(plant)

        counterpart.delete()
        diary_item.delete()

        source_diary.updated = timezone.now()
        target_diary.updated = timezone.now()
        source_diary.save(update_fields=["updated"])
        target_diary.save(update_fields=["updated"])

        self.recommendation_service.clear_cached_recommendation(request, diary_id=source_diary.pk)
        self.recommendation_service.clear_cached_recommendation(request, diary_id=target_diary.pk)
        return True, source_diary.pk

    def get(self, request, pk):
        with transaction.atomic():
            diary_item = get_object_or_404(DiaryItem.objects.select_related("diary"), pk=pk, diary__user=request.user)
            undone_transplant, redirect_diary_pk = self._undo_transplanted_item(request, diary_item)
            if undone_transplant:
                return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": redirect_diary_pk}))

            diary_pk = diary_item.diary_id
            diary = Diary.objects.select_for_update().get(pk=diary_item.diary_id, user=request.user)
            self._restore_plant_statuses_for_finished_item(diary_item)
            self.recommendation_service.clear_cached_recommendation(request, diary_id=diary_pk)
            diary_item.delete()
            diary.updated = timezone.now()
            diary.save(update_fields=["updated"])
            return HttpResponseRedirect(reverse("pro_auth:profile-diary-detail", kwargs={"pk": diary_pk}))
