from ckeditor.widgets import CKEditorWidget
from dal import autocomplete
from django import forms
from django.forms import BaseFormSet, ModelForm, formset_factory

from core.classifier.models import Category

from .models import DIARY_ITEM_ACTION_CHOICES, Diary, DiaryItem, Plant


def get_plant_category_queryset():
    return Category.objects.filter(
        is_active=True,
        parent__is_active=True,
        parent__is_diary_species_parent=True,
    ).order_by("value")


class DiaryForm(ModelForm):
    class Meta:
        model = Diary
        fields = ["title", "description"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["description"].widget = CKEditorWidget(config_name="public")
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
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.fields["existing_plant"].queryset = Plant.objects.filter(
            user=self.request.user,
            status="active",
        ).select_related("category")
        self.fields["plant_category"].queryset = get_plant_category_queryset()
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "profile-form-control")
        self.fields["plant_date"].widget.attrs.update({"type": "date"})

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
        super().__init__(*args, **kwargs)

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["request"] = self.request
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        has_plants = any(form.has_plant_data for form in self.forms if not form.cleaned_data.get("DELETE"))
        if not has_plants:
            raise forms.ValidationError("Додайте хоча б одну рослину до щоденника.")


PlantAttachmentFormSet = formset_factory(
    PlantAttachmentForm,
    formset=BasePlantAttachmentFormSet,
    extra=0,
    can_delete=True,
)


def save_diary_plants(diary, user, plant_formset):
    plants = []
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
            plants.append(plant)
            seen_plant_ids.add(plant.pk)

    diary.plants.set(plants)
    primary_plant = plants[0] if plants else None
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
        fields = ["plants", "description", "date", "image"]

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop("diary")
        super().__init__(*args, **kwargs)
        self.order_fields(["action_type", "plants", "description", "date", "image"])
        self.fields["plants"].widget = forms.CheckboxSelectMultiple()
        self.fields["plants"].queryset = self.diary.plants.filter(status="active")
        self.fields["plants"].required = False
        self.fields["plants"].label = "Рослини"
        self.fields["plants"].help_text = "За замовчуванням дія застосовується " "до всіх активних рослин."
        if not self.is_bound and "action_type" not in self.initial and self.instance and self.instance.pk:
            self.initial["action_type"] = self.instance.action_type
        if not self.is_bound and self.instance and self.instance.pk:
            selected_plants = self.instance.plants.all()
            self.initial["plants"] = selected_plants or self.fields["plants"].queryset
        elif not self.is_bound:
            self.initial["plants"] = self.fields["plants"].queryset
        self.fields["action_type"].widget.attrs.update(
            {
                "class": "profile-form-control profile-form-select",
            }
        )
        self.fields["description"].widget = CKEditorWidget(config_name="public")
        self.fields["description"].required = False
        self.fields["date"].widget.attrs.update(
            {
                "class": "profile-form-control",
                "type": "date",
            }
        )
        self.fields["image"].widget.attrs.update(
            {
                "class": "profile-form-control",
            }
        )

    def save(self, commit=True):
        self.instance.diary = self.diary
        self.instance.action_type = self.cleaned_data["action_type"]
        instance = super().save(commit=commit)
        if commit:
            plants = self.cleaned_data.get("plants") or self.diary.plants.filter(status="active")
            instance.plants.set(plants)
            if instance.action_type == "finished":
                plants.update(status="completed", completed_at=instance.date)
        return instance
