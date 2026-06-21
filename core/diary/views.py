import re
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from dal import autocomplete
from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.formats import date_format
from django.utils.http import url_has_allowed_host_and_scheme
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


def _format_harvest_amount(amount):
    normalized = amount.normalize()
    return format(normalized, "f").rstrip("0").rstrip(".")


def _build_harvest_summary(items):
    totals = OrderedDict()
    unit_labels = dict(DiaryItem._meta.get_field("harvest_unit").choices)
    for item in items:
        if item.action_type != "harvest" or item.harvest_amount is None or not item.harvest_unit:
            continue
        totals[item.harvest_unit] = totals.get(item.harvest_unit, Decimal("0")) + item.harvest_amount

    return [
        {
            "unit": unit,
            "label": unit_labels.get(unit, unit),
            "amount": amount,
            "display": f"{_format_harvest_amount(amount)} {unit_labels.get(unit, unit)}",
        }
        for unit, amount in totals.items()
    ]


def _build_profile_diary_dashboard(diaries, today=None):
    today = today or timezone.localdate()
    week_start = today - timedelta(days=6)
    attention_cutoff = today - timedelta(days=3)
    active_diaries = [diary for diary in diaries if not diary.is_archived]
    active_plants = []
    all_items = []
    actions_by_diary = []

    for diary in active_diaries:
        diary_plants = list(getattr(diary, "active_diary_plants", []))
        diary_items = list(getattr(diary, "latest_diary_items", []))
        active_plants.extend(diary_plants)
        all_items.extend(diary_items)
        recent_actions_count = sum(1 for item in diary_items if item.date and item.date >= week_start)
        actions_by_diary.append((recent_actions_count, diary))

    weekly_actions = [item for item in all_items if item.date and item.date >= week_start]
    watering_items = sorted(
        [item for item in all_items if item.action_type == "watering"],
        key=lambda item: (item.date, item.created),
        reverse=True,
    )
    last_watering = watering_items[0] if watering_items else None
    current_year_harvest_items = [
        item
        for item in all_items
        if item.action_type == "harvest" and item.date and item.date.year == today.year
    ]
    current_year_harvest_items.sort(
        key=lambda item: (item.date, item.created),
        reverse=True,
    )
    last_harvest = current_year_harvest_items[0] if current_year_harvest_items else None
    oldest_item_date = min((item.date for item in all_items if item.date), default=None)

    plant_last_watering = {}
    for item in watering_items:
        for plant in item.plants.all():
            if plant.pk not in plant_last_watering:
                plant_last_watering[plant.pk] = item

    plants_with_actions = set()
    for item in all_items:
        plants_with_actions.update(plant.pk for plant in item.plants.all())
    plants_without_actions = [plant for plant in active_plants if plant.pk not in plants_with_actions]

    plants_needing_attention = []
    for plant in active_plants:
        last_plant_watering = plant_last_watering.get(plant.pk)
        if last_plant_watering is None or last_plant_watering.date <= attention_cutoff:
            reason = (
                "поливу ще не було"
                if last_plant_watering is None
                else f"полив {date_format(last_plant_watering.date, 'j F')}"
            )
            plants_needing_attention.append(
                {
                    "plant": plant,
                    "reason": reason,
                    "last_watering": last_plant_watering,
                }
            )

    most_active_diary = None
    most_active_actions_count = 0
    if actions_by_diary:
        most_active_actions_count, most_active_diary = max(actions_by_diary, key=lambda item: item[0])
        if most_active_actions_count == 0:
            most_active_diary = None

    return {
        "active_plants_count": len(active_plants),
        "weekly_actions_count": len(weekly_actions),
        "last_watering": last_watering,
        "harvest_summary": _build_harvest_summary(current_year_harvest_items),
        "last_harvest": last_harvest,
        "plants_needing_attention": plants_needing_attention,
        "attention_count": len(plants_needing_attention),
        "plants_without_actions": plants_without_actions,
        "plants_without_actions_count": len(plants_without_actions),
        "most_active_diary": most_active_diary,
        "most_active_actions_count": most_active_actions_count,
        "oldest_item_date": oldest_item_date,
        "history_days_count": (today - oldest_item_date).days + 1 if oldest_item_date else 0,
        "week_start": week_start,
        "today": today,
    }


def _build_diary_detail_dashboard(diary, diary_items, active_plants, today=None):
    today = today or timezone.localdate()
    week_start = today - timedelta(days=6)
    weekly_actions = [item for item in diary_items if item.date and item.date >= week_start]
    weekly_watering = [item for item in weekly_actions if item.action_type == "watering"]
    watering_items = sorted(
        [item for item in diary_items if item.action_type == "watering"],
        key=lambda item: (item.date, item.created),
        reverse=True,
    )
    current_year_harvest_items = [
        item
        for item in diary_items
        if item.action_type == "harvest" and item.date and item.date.year == today.year
    ]
    oldest_item_date = min((item.date for item in diary_items if item.date), default=None)
    plants_with_actions = set()
    for item in diary_items:
        plants_with_actions.update(plant.pk for plant in item.plants.all())
    plants_without_actions = [plant for plant in active_plants if plant.pk not in plants_with_actions]

    return {
        "active_plants_count": len(active_plants),
        "entries_count": len(diary_items),
        "weekly_actions_count": len(weekly_actions),
        "weekly_watering_count": len(weekly_watering),
        "last_watering": watering_items[0] if watering_items else None,
        "harvest_summary": _build_harvest_summary(current_year_harvest_items),
        "plants_without_actions": plants_without_actions,
        "plants_without_actions_count": len(plants_without_actions),
        "oldest_item_date": oldest_item_date,
        "history_days_count": (today - oldest_item_date).days + 1 if oldest_item_date else 0,
        "week_start": week_start,
        "today": today,
        "diary": diary,
    }


def _attach_latest_items_to_plants(plants, diary_items):
    for plant in plants:
        plant.latest_diary_item = None

    plants_by_id = {plant.pk: plant for plant in plants}
    for item in diary_items:
        for plant in item.plants.all():
            if plant.pk in plants_by_id and plants_by_id[plant.pk].latest_diary_item is None:
                plants_by_id[plant.pk].latest_diary_item = item


def _attach_diary_list_summaries(diaries):
    for diary in diaries:
        diary_items = list(getattr(diary, "latest_diary_items", []))
        diary.last_diary_item = diary_items[0] if diary_items else None
        diary.diary_items_count = len(diary_items)


def _attach_diary_attention_flags(diaries, today=None):
    today = today or timezone.localdate()
    attention_cutoff = today - timedelta(days=3)

    for diary in diaries:
        diary.needs_attention = False
        if diary.is_archived:
            continue

        active_plants = list(getattr(diary, "active_diary_plants", []))
        if not active_plants:
            continue

        watering_items = sorted(
            [
                item
                for item in getattr(diary, "latest_diary_items", [])
                if item.action_type == "watering"
            ],
            key=lambda item: (item.date, item.created),
            reverse=True,
        )
        plant_last_watering = {}
        for item in watering_items:
            for plant in item.plants.all():
                if plant.pk not in plant_last_watering:
                    plant_last_watering[plant.pk] = item

        diary.needs_attention = any(
            plant_last_watering.get(plant.pk) is None
            or plant_last_watering[plant.pk].date <= attention_cutoff
            for plant in active_plants
        )


def _append_query_param(url, param):
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{param}"


def _get_safe_redirect_url(request, fallback_url):
    next_url = request.POST.get("next", "").strip()
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return fallback_url


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
            "plants": [selected_plant],
        }

    if item.apply_to_all:
        return {
            "label": "усіх активних рослин",
            "plant_name": "усіх активних рослин",
            "plant_date": None,
            "plants": target_plants,
        }

    if len(target_plants) == 1:
        plant = target_plants[0]
        return {
            "label": plant.display_name,
            "plant_name": plant.display_name,
            "plant_date": plant.plant_date,
            "plants": [plant],
        }

    if len(target_plants) <= 2:
        label = ", ".join(plant.display_name for plant in target_plants)
        return {
            "label": label,
            "plant_name": label,
            "plant_date": None,
            "plants": target_plants,
        }

    return {
        "label": f"{len(target_plants)} рослин",
        "plant_name": ", ".join(plant.display_name for plant in target_plants[:3]),
        "plant_date": None,
        "plants": target_plants,
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
        _attach_diary_list_summaries(diaries)
        _attach_diary_attention_flags(diaries)
        for diary in diaries:
            if not diary.is_archived:
                diary.diary_item_form = DiaryItemForm(diary=diary, prefix=f"diary-{diary.pk}")
        context["active_diaries"] = [diary for diary in diaries if not diary.is_archived]
        context["archived_diaries"] = [diary for diary in diaries if diary.is_archived]
        context["attention_diaries"] = [
            diary for diary in context["active_diaries"] if diary.needs_attention
        ]
        context["diary_dashboard"] = _build_profile_diary_dashboard(diaries)
        return context


class ProfilePlantListView(ListView):
    template_name = "diary/profile/plant_list.html"
    context_object_name = "plants"

    def get_queryset(self):
        return (
            Plant.objects.filter(user=self.request.user)
            .select_related("category")
            .prefetch_related(
                Prefetch(
                    "diaries",
                    queryset=Diary.objects.filter(user=self.request.user).order_by("-updated"),
                    to_attr="profile_diaries",
                ),
                Prefetch(
                    "diary_items",
                    queryset=DiaryItem.objects.select_related("diary").order_by("-date", "-created"),
                    to_attr="profile_diary_items",
                ),
            )
            .order_by("status", "-plant_date", "id")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        plants = list(context["plants"])
        today = timezone.localdate()
        for plant in plants:
            plant.latest_diary_item = (
                plant.profile_diary_items[0]
                if plant.profile_diary_items
                else None
            )
            plant.diary_items_count = len(plant.profile_diary_items)
            lifecycle_end = plant.completed_at or today
            plant.age_days = max((lifecycle_end - plant.plant_date).days, 0)

        context["plants"] = plants
        context["active_plants"] = [plant for plant in plants if plant.status == "active"]
        context["completed_plants"] = [plant for plant in plants if plant.status == "completed"]
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
        all_diary_items = list(self.object.diary_items.all())
        _attach_latest_items_to_plants(active_diary_plants, all_diary_items)
        _attach_latest_items_to_plants(completed_diary_plants, all_diary_items)
        for plant in active_diary_plants:
            plant.move_form = PlantMoveForm(
                user=self.request.user,
                source_diary=self.object,
                plant=plant,
                prefix=f"plant-{plant.pk}",
            )
        selected_plant_id = self.request.GET.get("plant", "")
        selected_period = self.request.GET.get("period", "").strip()
        diary_filter_plants = _build_diary_filter_plants(self.object)

        context["diary_items"] = diary_items
        context["grouped_diary_items"] = grouped_diary_items
        context["diary_plants"] = self.object.plants.all()
        context["diary_filter_plants"] = diary_filter_plants
        context["active_diary_plants"] = active_diary_plants
        context["completed_diary_plants"] = completed_diary_plants
        context["diary_detail_dashboard"] = _build_diary_detail_dashboard(
            self.object,
            all_diary_items,
            active_diary_plants,
        )
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
        context["diary_item_form"] = DiaryItemForm(diary=self.object)
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
                        "note": item.description,
                        "has_photo": bool(item.image),
                    }
                    for item in diary_items[:20]
                ],
                has_photo=bool(latest_item.image),
                plants=recommendation_target["plants"],
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
        form_prefix = self.request.POST.get("_form_prefix", "").strip()
        if self.request.method == "POST" and form_prefix:
            kwargs["prefix"] = form_prefix
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
                    "note": item.description,
                    "has_photo": bool(item.image),
                }
                for item in diary_items[:20]
            ],
            has_photo=bool(form.instance.image),
            plants=recommendation_target["plants"],
            use_ai=True,
        )
        self.recommendation_service.cache_recommendation(
            self.request,
            diary_id=diary.id,
            item_id=form.instance.id,
            recommendation=recommendation,
        )
        diary.save(update_fields=["updated"])
        fallback_url = reverse("pro_auth:profile-diary-detail", kwargs={"pk": diary.pk})
        return HttpResponseRedirect(_get_safe_redirect_url(self.request, fallback_url))


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


class QuickWateringView(View):
    def post(self, request, pk):
        diary = get_object_or_404(Diary, pk=pk, user=request.user, is_archived=False)
        active_plants = diary.plants.filter(status="active")
        redirect_url = _get_safe_redirect_url(request, reverse("pro_auth:profile-diary-list"))

        if not active_plants.exists():
            return HttpResponseRedirect(_append_query_param(redirect_url, "quick_action=watering_empty"))

        apply_to_all = request.POST.get("apply_to_all") == "1"
        selected_plant_ids = request.POST.getlist("plants")

        if apply_to_all:
            target_plants = active_plants
        else:
            target_plants = active_plants.filter(pk__in=selected_plant_ids)
            if not target_plants.exists():
                return HttpResponseRedirect(_append_query_param(redirect_url, "quick_action=watering_missing_plants"))

        diary_item = DiaryItem.objects.create(
            diary=diary,
            action_type="watering",
            apply_to_all=apply_to_all,
            description="",
            date=timezone.localdate(),
        )
        diary_item.plants.set(target_plants)
        diary.updated = timezone.now()
        diary.save(update_fields=["updated"])
        return HttpResponseRedirect(_append_query_param(redirect_url, "quick_action=watering_added"))


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
        form_prefix = self.request.POST.get("_form_prefix", "").strip()
        if self.request.method == "POST" and form_prefix:
            kwargs["prefix"] = form_prefix
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
