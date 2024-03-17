from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView

from .forms import AdminParseForm
from .models import Company, Product
from .parser import get_content_from_url, parse_data_from_content


class CompanyListView(ListView):
    model = Company
    template_name = "companies/list.html"
    context_object_name = "companies"

    def get_queryset(self):
        return Company.objects.filter(active=True)


class CompanyDetailView(DetailView):
    model = Company
    template_name = "companies/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["products"] = Product.objects.filter(company=self.object)
        return context


def admin_parse_form_view(request, company_id: int):
    if request.method == "POST":
        form = AdminParseForm(request.POST, request.FILES)
        if form.is_valid():
            # get company
            company = Company.objects.get(id=company_id)
            objects = []
            # process the form
            if form.cleaned_data.get("url"):
                # parse from url
                content = get_content_from_url(form.cleaned_data.get("url"))
                # parse content
                objects = parse_data_from_content(
                    content, form.cleaned_data.get("custom_parser_map") or company.parser_map
                )
            else:
                # parse from file
                for file in request.FILES.getlist("files"):
                    content = file.read().decode("utf-8")
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
                _to_save.append(Product(company_id=company.id, **obj))
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
