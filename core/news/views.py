from datetime import datetime

from django.views.generic import ListView

from .models import News


class NewsListView(ListView):
    paginate_by = 50
    model = News
    template_name = "news/list.html"

    def get_queryset(self):
        qs = News.objects.all()
        if self.request.GET.get("from"):
            qs = qs.filter(date__gte=datetime.fromtimestamp(int(self.request.GET.get("from"))))
        return qs.order_by('-date')
