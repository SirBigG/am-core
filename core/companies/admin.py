from django.contrib import admin

from .models import Company, Product

class ProductInline(admin.TabularInline):
    model = Product
    extra = 1

class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'logo', 'active', 'website', 'location')
    list_filter = ('active', )
    search_fields = ('name', 'description')
    raw_id_fields = ('location',)
    inlines = [ProductInline]

admin.site.register(Company, CompanyAdmin)
admin.site.register(Product)
