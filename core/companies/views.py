from django.views.generic import ListView, DetailView

from .models import Company, Product

class CompanyListView(ListView):
    model = Company
    template_name = 'companies/list.html'
    context_object_name = 'companies'

    def get_queryset(self):
        return Company.objects.filter(active=True)


class CompanyDetailView(DetailView):
    model = Company
    template_name = 'companies/detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['products'] = Product.objects.filter(company=self.object)
        return context
