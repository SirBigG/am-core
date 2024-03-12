from django.contrib import admin

from .forms import CompanyForm, ProductForm
from .models import Company, Product


class ProductInline(admin.TabularInline):
    form = ProductForm
    model = Product
    extra = 3


class CompanyAdmin(admin.ModelAdmin):
    form = CompanyForm
    list_display = ("name", "description", "logo", "active", "website", "location")
    list_filter = ("active",)
    search_fields = ("name", "description")
    inlines = [ProductInline]


admin.site.register(Company, CompanyAdmin)
admin.site.register(Product)
