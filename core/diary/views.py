from django.views.generic import ListView, DetailView

from .models import Diary


class DiaryListView(ListView):
    template_name = "diary/list.html"
    model = Diary
    paginate_by = 50
    ordering = "-created"

    def get_queryset(self):
        return Diary.objects.filter(public=True)


class DiaryDetailView(DetailView):
    model = Diary
    template_name = "diary/detail.html"

    def get_queryset(self):
        return Diary.objects.filter(user=self.request.user)
