from ckeditor.widgets import CKEditorWidget
from django import forms
from django.forms import ModelForm

from .models import DIARY_ITEM_ACTION_CHOICES, PLANT_TYPE_CHOICES, Diary, DiaryItem


class DiaryForm(ModelForm):
    plant_type = forms.ChoiceField(
        label="Вид рослини",
        choices=PLANT_TYPE_CHOICES,
    )
    plant_date = forms.DateField(
        label="Дата",
        initial=forms.fields.datetime.date.today,
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )

    class Meta:
        model = Diary
        fields = ["title", "description"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)
        self.order_fields(["plant_type", "plant_date", "title", "description"])
        self.fields["description"].widget = CKEditorWidget(config_name="public")
        if not self.is_bound and "plant_type" not in self.initial and self.instance and self.instance.pk:
            self.initial["plant_type"] = self.instance.plant_type
        if not self.is_bound and "plant_date" not in self.initial:
            if self.instance and self.instance.pk and self.instance.plant_date:
                self.initial["plant_date"] = self.instance.plant_date.isoformat()
            else:
                self.initial["plant_date"] = forms.fields.datetime.date.today().isoformat()
        self.fields["title"].label = "Сорт рослини"
        self.fields["title"].widget.attrs.update(
            {
                "class": "profile-form-control",
                "placeholder": "Наприклад, Cherry",
            }
        )
        self.fields["plant_type"].widget.attrs.update(
            {
                "class": "profile-form-control profile-form-select",
            }
        )
        self.fields["plant_date"].widget.attrs.update(
            {
                "class": "profile-form-control",
            }
        )

    def save(self, commit=True):
        self.instance.user = self.request.user
        self.instance.plant_type = self.cleaned_data["plant_type"]
        self.instance.plant_date = self.cleaned_data["plant_date"]
        instance = super().save(commit=commit)
        return instance


class DiaryItemForm(ModelForm):
    action_type = forms.ChoiceField(
        label="Оберіть швидку дію",
        choices=DIARY_ITEM_ACTION_CHOICES,
    )

    class Meta:
        model = DiaryItem
        fields = ["description", "date", "image"]

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop("diary")
        super().__init__(*args, **kwargs)
        self.order_fields(["action_type", "description", "date", "image"])
        if not self.is_bound and "action_type" not in self.initial and self.instance and self.instance.pk:
            self.initial["action_type"] = self.instance.action_type
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
        return instance
