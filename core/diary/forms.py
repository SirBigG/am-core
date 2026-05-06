from dal import autocomplete
from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import BaseFormSet, ModelForm, formset_factory
from django.utils import timezone

from core.classifier.models import Category

from .models import DIARY_ITEM_ACTION_CHOICES, Diary, DiaryItem, Plant

PLANT_DELETE_CONFIRM_TEXT = "Видалити рослину? Ця рослина ще не має історії. Її буде повністю видалено."
PLANT_FINISH_CONFIRM_TEXT = (
    "Завершити цикл рослини? "
    "Ця рослина має історію у щоденнику. Вона буде позначена як завершена "
    "і залишиться доступною в історії та фільтрах. "
    "Ви впевнені?"
)
PLANT_BLOCKED_TEXT = (
    "Ця рослина використовується в інших щоденниках. "
    "Для неї потрібен окремий сценарій перенесення або керування."
)


def get_existing_plant_remove_state(diary, plant):
    if diary is None or plant is None:
        return {"mode": "row", "message": ""}

    if plant.status == "completed":
        return {"mode": "blocked", "message": PLANT_BLOCKED_TEXT}

    is_attached_to_current_diary = plant.diaries.filter(pk=diary.pk).exists()
    has_history_in_current_diary = plant.diary_items.filter(diary=diary).exists()
    has_history_elsewhere = plant.diary_items.exclude(diary=diary).exists()
    attached_to_other_diaries = plant.diaries.exclude(pk=diary.pk).exists()

    if not is_attached_to_current_diary or attached_to_other_diaries or has_history_elsewhere:
        return {"mode": "blocked", "message": PLANT_BLOCKED_TEXT}

    if has_history_in_current_diary:
        return {"mode": "finish", "message": PLANT_FINISH_CONFIRM_TEXT}

    return {"mode": "delete", "message": PLANT_DELETE_CONFIRM_TEXT}


def get_plant_category_queryset():
    return Category.objects.filter(
        is_active=True,
        parent__is_active=True,
        parent__value="Рослинництво",
    ).order_by("value")


class DiaryForm(ModelForm):
    class Meta:
        model = Diary
        fields = ["title", "description"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 5})
        self.fields["title"].label = "Назва щоденника"
        self.fields["title"].widget.attrs.update(
            {
                "class": "profile-form-control",
                "placeholder": "Наприклад, Помідори на балконі",
            }
        )
        self.fields["description"].widget.attrs.update(
            {
                "class": "profile-form-control",
                "placeholder": "Коротко опишіть цей щоденник",
            }
        )

    def save(self, commit=True):
        self.instance.user = self.request.user
        return super().save(commit=commit)


class PlantAttachmentForm(forms.Form):
    existing_plant = forms.ModelChoiceField(
        label="Обрати існуючу рослину",
        queryset=Plant.objects.none(),
        required=False,
        empty_label="Почніть вводити назву, сорт або категорію",
        widget=autocomplete.ModelSelect2(
            url="diaries:plant-autocomplete",
            attrs={
                "class": "profile-form-control profile-form-select",
                "data-placeholder": "Почніть вводити назву, сорт або категорію",
            },
        ),
    )
    plant_category = forms.ModelChoiceField(
        label="Категорія рослини",
        queryset=Category.objects.none(),
        required=False,
        empty_label="Оберіть категорію",
        widget=autocomplete.ModelSelect2(
            url="diary-plant-category-autocomplete",
            attrs={
                "class": "profile-form-control profile-form-select",
                "data-placeholder": "Почніть вводити категорію",
            },
        ),
    )
    plant_variety = forms.CharField(label="Сорт", required=False, max_length=255)
    plant_title = forms.CharField(label="Назва рослини", required=False, max_length=255)
    plant_description = forms.CharField(
        label="Опис рослини",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    plant_date = forms.DateField(
        label="Дата посадки",
        required=False,
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "text",
                "data-profile-datepicker": "true",
                "autocomplete": "off",
                "placeholder": "ДД.ММ.РРРР",
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        self.diary = kwargs.pop("diary", None)
        super().__init__(*args, **kwargs)
        self.remove_mode = "row"
        self.remove_message = ""
        self.remove_label = "Прибрати"
        self.remove_is_disabled = False
        self.fields["existing_plant"].queryset = Plant.objects.filter(
            user=self.request.user,
            status="active",
        ).select_related("category")
        self.fields["plant_category"].queryset = get_plant_category_queryset()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "profile-form-control")
        self.fields["plant_date"].initial = timezone.localdate()
        self.fields["plant_date"].widget.attrs.update(
            {
                "type": "text",
                "data-profile-datepicker": "true",
                "autocomplete": "off",
                "placeholder": "ДД.ММ.РРРР",
            }
        )
        existing_plant = self._get_existing_plant_for_state()
        if existing_plant is not None:
            remove_state = get_existing_plant_remove_state(self.diary, existing_plant)
            self.remove_mode = remove_state["mode"]
            self.remove_message = remove_state["message"]
        if self.remove_mode == "delete":
            self.remove_label = "Видалити"
        elif self.remove_mode == "finish":
            self.remove_label = "Завершити цикл"
        elif self.remove_mode == "blocked":
            self.remove_label = "Потрібне перенесення"
            self.remove_is_disabled = True

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data

        existing_plant = cleaned_data.get("existing_plant")
        plant_category = cleaned_data.get("plant_category")
        plant_variety = cleaned_data.get("plant_variety", "").strip()
        plant_title = cleaned_data.get("plant_title", "").strip()
        plant_description = cleaned_data.get("plant_description", "").strip()
        creates_plant = bool(plant_category or plant_variety or plant_title)

        if existing_plant and (creates_plant or plant_description):
            message = "В одному рядку оберіть існуючу рослину " "або створіть нову."
            raise forms.ValidationError(
                message,
            )

        if plant_description and not creates_plant:
            raise forms.ValidationError("Для нової рослини заповніть категорію, сорт або назву.")

        cleaned_data["plant_variety"] = plant_variety
        cleaned_data["plant_title"] = plant_title
        cleaned_data["plant_description"] = plant_description
        return cleaned_data

    def _get_existing_plant_for_state(self):
        plant_id = None
        if self.is_bound:
            plant_id = self.data.get(self.add_prefix("existing_plant"))
        if not plant_id:
            plant_id = self.initial.get("existing_plant")
        if not plant_id:
            return None
        return Plant.objects.filter(pk=plant_id).first()

    @property
    def has_plant_data(self):
        if not hasattr(self, "cleaned_data"):
            return False
        return bool(
            self.cleaned_data.get("existing_plant")
            or self.cleaned_data.get("plant_category")
            or self.cleaned_data.get("plant_variety")
            or self.cleaned_data.get("plant_title")
        )


class BasePlantAttachmentFormSet(BaseFormSet):
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        self.allow_empty = kwargs.pop("allow_empty", False)
        self.diary = kwargs.pop("diary", None)
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["request"] = self.request
        kwargs["diary"] = self.diary
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        has_plants = any(form.has_plant_data for form in self.forms if not form.cleaned_data.get("DELETE"))
        blocked_remove_errors = []
        for form in self.forms:
            if not form.cleaned_data.get("DELETE"):
                continue
            existing_plant = form.cleaned_data.get("existing_plant")
            if existing_plant is None:
                continue
            remove_state = get_existing_plant_remove_state(self.diary, existing_plant)
            if remove_state["mode"] == "blocked":
                blocked_remove_errors.append(remove_state["message"])

        if blocked_remove_errors:
            raise forms.ValidationError(blocked_remove_errors)

        if not has_plants and not self.allow_empty:
            raise forms.ValidationError("Додайте хоча б одну рослину до щоденника.")


PlantAttachmentFormSet = formset_factory(
    PlantAttachmentForm,
    formset=BasePlantAttachmentFormSet,
    extra=0,
    can_delete=True,
)


def save_diary_plants(diary, user, plant_formset):
    with transaction.atomic():
        plants_to_finish = []
        plants_to_delete = []

        for form in plant_formset.forms:
            if not form.cleaned_data.get("DELETE"):
                continue

            existing_plant = form.cleaned_data.get("existing_plant")
            if existing_plant is None:
                continue

            remove_state = get_existing_plant_remove_state(diary, existing_plant)
            if remove_state["mode"] == "blocked":
                raise ValidationError(remove_state["message"])
            if remove_state["mode"] == "finish":
                plants_to_finish.append(existing_plant)
            elif remove_state["mode"] == "delete":
                plants_to_delete.append(existing_plant)

        active_plants = []
        seen_plant_ids = set()

        for form in plant_formset.forms:
            if form.cleaned_data.get("DELETE") or not form.has_plant_data:
                continue

            plant = form.cleaned_data.get("existing_plant")
            if plant is None:
                plant = Plant.objects.create(
                    user=user,
                    category=form.cleaned_data.get("plant_category"),
                    variety=form.cleaned_data.get("plant_variety", ""),
                    title=form.cleaned_data.get("plant_title", ""),
                    description=form.cleaned_data.get("plant_description", ""),
                    plant_date=form.cleaned_data.get("plant_date") or forms.fields.datetime.date.today(),
                )

            if plant.pk not in seen_plant_ids:
                active_plants.append(plant)
                seen_plant_ids.add(plant.pk)

        today = timezone.localdate()
        for plant in plants_to_finish:
            if plant.status != "completed":
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

        for plant in plants_to_delete:
            if diary.plants.filter(pk=plant.pk).exists():
                diary.plants.remove(plant)
            plant.delete()

        completed_plants = list(diary.plants.filter(status="completed"))
        for plant in completed_plants:
            if plant.pk not in seen_plant_ids:
                active_plants.append(plant)
                seen_plant_ids.add(plant.pk)

        diary.plants.set(active_plants)
        primary_plant = next((plant for plant in active_plants if plant.status == "active"), None)
    if primary_plant:
        diary.plant_type = primary_plant.category.slug if primary_plant.category_id else ""
        diary.plant_date = primary_plant.plant_date
        diary.save(update_fields=["plant_type", "plant_date"])


class DiaryItemForm(ModelForm):
    action_type = forms.ChoiceField(
        label="Оберіть швидку дію",
        choices=DIARY_ITEM_ACTION_CHOICES,
    )

    class Meta:
        model = DiaryItem
        fields = ["apply_to_all", "plants", "description", "date", "image"]

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop("diary")
        super().__init__(*args, **kwargs)
        self.order_fields(["action_type", "apply_to_all", "plants", "description", "date", "image"])
        if not (self.instance and self.instance.pk):
            self.fields["action_type"].choices = [
                choice
                for choice in DIARY_ITEM_ACTION_CHOICES
                if choice[0] not in {"planted", "transplanted"}
            ]
        self.fields["apply_to_all"].label = "Застосувати до всіх активних рослин"
        self.fields["apply_to_all"].required = False
        self.fields["plants"].widget = forms.CheckboxSelectMultiple()
        self.fields["plants"].queryset = self.diary.plants.filter(status="active")
        self.fields["plants"].required = False
        self.fields["plants"].label = "Рослини"
        self.fields["plants"].help_text = "Оберіть одну або кілька рослин, якщо дія не для всіх."
        if not self.is_bound and "action_type" not in self.initial and self.instance and self.instance.pk:
            self.initial["action_type"] = self.instance.action_type
        if not self.is_bound and "apply_to_all" not in self.initial:
            self.initial["apply_to_all"] = self.instance.apply_to_all if self.instance and self.instance.pk else True
        if not self.is_bound and self.instance and self.instance.pk:
            self.initial["plants"] = self.instance.plants.all()
        self.fields["action_type"].widget.attrs.update(
            {
                "class": "profile-form-control profile-form-select",
            }
        )
        self.fields["description"].widget = forms.Textarea(attrs={"rows": 5})
        self.fields["description"].required = False
        self.fields["description"].widget.attrs.update(
            {
                "class": "profile-form-control",
                "placeholder": "Додайте опис дії",
            }
        )
        self.fields["date"].widget = forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "class": "profile-form-control",
                "type": "text",
                "data-profile-datepicker": "true",
                "autocomplete": "off",
                "placeholder": "ДД.ММ.РРРР",
            },
        )
        self.fields["image"].widget.attrs.update(
            {
                "class": "profile-form-control",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        active_plants_qs = self.diary.plants.filter(status="active")
        apply_to_all = cleaned_data.get("apply_to_all", False)
        selected_plants = cleaned_data.get("plants")

        if not active_plants_qs.exists():
            raise forms.ValidationError(
                "У цьому щоденнику немає активних рослин. Додайте нову рослину, щоб створити дію."
            )

        if not apply_to_all and not selected_plants:
            self.add_error("plants", "Оберіть хоча б одну рослину або застосуйте дію до всіх активних рослин.")

        return cleaned_data

    def save(self, commit=True):
        self.instance.diary = self.diary
        self.instance.action_type = self.cleaned_data["action_type"]
        self.instance.apply_to_all = self.cleaned_data["apply_to_all"]
        instance = super().save(commit=commit)
        if commit:
            if self.cleaned_data["apply_to_all"]:
                plants = self.diary.plants.filter(status="active")
            else:
                plants = self.cleaned_data["plants"]
            instance.plants.set(plants)
            if instance.action_type == "finished":
                plants.update(status="completed", completed_at=instance.date)
        return instance


class PlantingForm(forms.Form):
    plant_category = forms.ModelChoiceField(
        label="Категорія рослини",
        queryset=Category.objects.none(),
        required=False,
        empty_label="Оберіть категорію",
        widget=autocomplete.ModelSelect2(
            url="diary-plant-category-autocomplete",
            attrs={
                "class": "profile-form-control profile-form-select",
                "data-placeholder": "Почніть вводити категорію",
            },
        ),
    )
    plant_variety = forms.CharField(label="Сорт", required=False, max_length=255)
    plant_title = forms.CharField(label="Назва рослини", required=False, max_length=255)
    plant_description = forms.CharField(
        label="Нотатка до посадки",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    plant_date = forms.DateField(
        label="Дата посадки",
        required=True,
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={
                "type": "text",
                "data-profile-datepicker": "true",
                "autocomplete": "off",
                "placeholder": "ДД.ММ.РРРР",
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.diary = kwargs.pop("diary")
        super().__init__(*args, **kwargs)
        self.fields["plant_category"].queryset = get_plant_category_queryset()
        self.fields["plant_date"].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "profile-form-control")
        self.fields["plant_date"].widget.attrs.update(
            {
                "type": "text",
                "data-profile-datepicker": "true",
                "autocomplete": "off",
                "placeholder": "ДД.ММ.РРРР",
            }
        )

    def clean(self):
        cleaned_data = super().clean()
        plant_category = cleaned_data.get("plant_category")
        plant_variety = (cleaned_data.get("plant_variety") or "").strip()
        plant_title = (cleaned_data.get("plant_title") or "").strip()
        plant_description = (cleaned_data.get("plant_description") or "").strip()

        if not (plant_category or plant_variety or plant_title):
            raise forms.ValidationError("Заповніть категорію, сорт або назву рослини.")

        cleaned_data["plant_variety"] = plant_variety
        cleaned_data["plant_title"] = plant_title
        cleaned_data["plant_description"] = plant_description
        return cleaned_data

    def save(self):
        with transaction.atomic():
            plant = Plant.objects.create(
                user=self.user,
                category=self.cleaned_data.get("plant_category"),
                variety=self.cleaned_data.get("plant_variety", ""),
                title=self.cleaned_data.get("plant_title", ""),
                description=self.cleaned_data.get("plant_description", ""),
                plant_date=self.cleaned_data["plant_date"],
            )
            self.diary.plants.add(plant)

            planted_item = DiaryItem.objects.create(
                diary=self.diary,
                action_type="planted",
                apply_to_all=False,
                date=self.cleaned_data["plant_date"],
                description=self.cleaned_data.get("plant_description", ""),
            )
            planted_item.plants.set([plant])

            if not self.diary.plants.exclude(pk=plant.pk).filter(status="active").exists():
                self.diary.plant_type = plant.category.slug if plant.category_id else ""
                self.diary.plant_date = plant.plant_date

            self.diary.updated = timezone.now()
            self.diary.save(update_fields=["plant_type", "plant_date", "updated"])
        return plant


class PlantMoveForm(forms.Form):
    target_diary = forms.ModelChoiceField(
        label="Перенести в щоденник",
        queryset=Diary.objects.none(),
        empty_label="Оберіть щоденник",
        widget=forms.Select(
            attrs={
                "class": "profile-form-control profile-form-select",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.source_diary = kwargs.pop("source_diary")
        self.plant = kwargs.pop("plant")
        super().__init__(*args, **kwargs)
        self.fields["target_diary"].queryset = Diary.objects.filter(
            user=self.user,
            is_archived=False,
        ).exclude(pk=self.source_diary.pk)
        self.fields["target_diary"].label_from_instance = lambda diary: diary.title

    def clean_target_diary(self):
        target_diary = self.cleaned_data["target_diary"]
        if target_diary.pk == self.source_diary.pk:
            raise forms.ValidationError("Оберіть інший щоденник для перенесення.")
        if target_diary.is_archived:
            raise forms.ValidationError("Не можна перенести рослину в архівний щоденник.")
        return target_diary
