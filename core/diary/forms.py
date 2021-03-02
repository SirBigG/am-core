from django.forms import ModelForm

from .models import Diary, DiaryItem


class DiaryForm(ModelForm):
    class Meta:
        model = Diary
        fields = ["title", "description", "public"]

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.user = self.request.user
        instance = super().save(commit=commit)
        return instance


class DiaryItemForm(ModelForm):
    class Meta:
        model = DiaryItem
        fields = ["description", "image"]

    def __init__(self, *args, **kwargs):
        self.diary = kwargs.pop("diary")
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.diary = self.diary
        instance = super().save(commit=commit)
        return instance
