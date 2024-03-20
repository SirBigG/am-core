from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .forms import CompanyForm, ProductForm
from .models import Company, Product


class ProductInline(admin.TabularInline):
    form = ProductForm
    model = Product
    extra = 1


class NullPostFilter(admin.SimpleListFilter):
    title = _("post status")
    parameter_name = "post"

    def lookups(self, request, model_admin):
        return [
            ("Null", _("Null")),
            ("Not Null", _("Not Null")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "Null":
            return queryset.filter(post__isnull=True)

        if self.value() == "Not Null":
            return queryset.filter(post__isnull=False)
        return queryset


class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    autocomplete_fields = ["post"]
    list_display = ("name", "post", "price", "description", "auction_price", "currency", "active")
    list_filter = (NullPostFilter, "active", "company")
    list_editable = ("post", "auction_price", "price", "currency", "active")
    search_fields = ("name", "description", "post__title")

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields["post"].widget.can_add_related = False
        return form


class CompanyAdmin(admin.ModelAdmin):
    form = CompanyForm
    list_display = ("name", "description", "logo", "active", "website", "location")
    list_filter = ("active",)
    search_fields = ("name", "description")
    # inlines = [ProductInline]


admin.site.register(Company, CompanyAdmin)
admin.site.register(Product, ProductAdmin)
