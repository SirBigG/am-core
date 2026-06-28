from django.conf import settings
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import CompanyForm, LinkForm, ProductForm
from .models import Company, Link, ParserSourceAttempt, Product, ProductPriceHistory
from .parser import parse_many_links_with_same_browser


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


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    autocomplete_fields = ["post"]
    list_display = ("name", "post", "price", "price_updated_at", "description", "auction_price", "currency", "active")
    list_filter = (NullPostFilter, "active", "company", "source_link")
    list_editable = ("post", "auction_price", "price", "currency", "active")
    search_fields = ("name", "description", "post__title", "source_product_key", "link")

    def get_form(self, request, obj=None, change=False, **kwargs):
        form = super().get_form(request, obj, change, **kwargs)
        form.base_fields["post"].widget.can_add_related = False
        return form

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyForm
    list_display = ("name", "type", "logo_img", "active", "website", "location", "latitude", "longitude")
    list_filter = ("active", "type")
    search_fields = ("name", "description")

    @admin.display(description=_("logo"))
    def logo_img(self, obj):
        url = obj.logo.url if obj.logo else None
        if url:
            return format_html('<img src="{}" width="100" height="50" />', url)
        return ""

    def has_delete_permission(self, request, obj=None):
        return False


def parse_link(modeladmin, request, queryset):
    if not settings.ENABLE_IN_PROCESS_COMPANY_PARSING:
        modeladmin.message_user(
            request,
            _("In-process company parsing is disabled. Use a trusted local parser worker instead."),
            level=messages.WARNING,
        )
        return
    # for link in queryset:
    #     link.parse()
    parse_many_links_with_same_browser(queryset)


@admin.register(Link)
class LinkAdmin(admin.ModelAdmin):
    list_display = (
        "url",
        "company",
        "category",
        "experiment_label",
        "source_type",
        "priority",
        "leased_by",
        "leased_until",
        "last_crawled",
        "last_success_at",
        "last_product_count",
        "active",
    )
    list_filter = (
        "active",
        "company",
        "category",
        "experiment_label",
        "source_type",
    )
    list_editable = ("active",)
    search_fields = ("url", "company__name", "experiment_label", "last_error")
    actions = [parse_link]
    form = LinkForm

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not settings.ENABLE_IN_PROCESS_COMPANY_PARSING:
            actions.pop("parse_link", None)
        return actions

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductPriceHistory)
class ProductPriceHistoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "source_link",
        "price",
        "min_price",
        "max_price",
        "currency",
        "observed_at",
        "worker_name",
    )
    list_filter = ("currency", "source_link", "worker_name")
    search_fields = ("product__name", "source_link__url", "raw_price")
    readonly_fields = ("created",)


@admin.register(ParserSourceAttempt)
class ParserSourceAttemptAdmin(admin.ModelAdmin):
    list_display = ("source_link", "worker_name", "status", "crawl_status", "product_count", "created")
    list_filter = ("status", "worker_name", "source_link")
    search_fields = ("source_link__url", "worker_name", "error")
    readonly_fields = ("created",)
