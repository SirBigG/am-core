from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView

from core.classifier.models import Category, Region

from .forms import AdminParseForm
from .models import Company, CompanyType, Product
from .parser import get_content_from_url, parse_data_from_content


class CompanyListView(ListView):
    model = Company
    template_name = "companies/list.html"
    context_object_name = "companies"
    paginate_by = 24

    def get_queryset(self):
        queryset = Company.objects.filter(active=True, type=CompanyType.SHOP)
        category = self.request.GET.get("category", "")
        region = self.request.GET.get("region", "")
        if category:
            queryset = queryset.filter(products__category__slug=category, products__active=True)
        if region:
            queryset = queryset.filter(location__region__slug=region)
        return queryset.distinct().order_by("name", "pk")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shops = Company.objects.filter(active=True, type=CompanyType.SHOP)
        context.update(
            market_tab="companies",
            company_categories=Category.objects.filter(product__company__in=shops, product__active=True, is_active=True)
            .distinct()
            .order_by("value"),
            company_regions=Region.objects.filter(location__company__in=shops).distinct().order_by("value"),
        )
        return context


class CompanyDetailView(DetailView):
    model = Company
    template_name = "companies/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["products"] = Product.objects.filter(company=self.object, active=True)
        return context


def admin_parse_form_view(request, company_id: int):
    if not settings.ENABLE_IN_PROCESS_COMPANY_PARSING:
        raise PermissionDenied("In-process company parsing is disabled.")

    if request.method == "POST":
        form = AdminParseForm(request.POST, request.FILES)
        if form.is_valid():
            # get company
            company = Company.objects.get(id=company_id)
            objects = []
            parser_map = form.cleaned_data.get("custom_parser_map") or company.parser_map or {}
            # process the form
            if form.cleaned_data.get("url"):
                # parse from url
                content = get_content_from_url(form.cleaned_data.get("url"), encoding=parser_map.get("encoding"))
                # parse content
                objects = parse_data_from_content(
                    content, form.cleaned_data.get("custom_parser_map") or company.parser_map
                )
            else:
                # parse from file
                for file in request.FILES.getlist("files"):
                    content = file.read()
                    if not parser_map.get("encoding"):
                        content = content.decode("utf-8")
                    # parse content
                    objects.extend(
                        parse_data_from_content(
                            content,
                            form.cleaned_data.get("custom_parser_map") or company.parser_map,
                        )
                    )

            # save objects
            _to_save = []
            for obj in objects:
                _to_save.append(Product(company_id=company.id, category=form.cleaned_data.get("category"), **obj))
            for obj in _to_save:
                # Check if price is decimal
                if obj.price:
                    try:
                        obj.price = float(obj.price)
                    except ValueError:
                        obj.price = None
            Product.objects.bulk_create(_to_save)
            # Redirect to admin company edit page
            return redirect("admin:companies_company_change", company.id)
    else:
        form = AdminParseForm()

    return render(request, "companies/admin_parse_form.html", {"form": form})
