from django.conf import settings
from django.contrib import admin, messages
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.template.response import TemplateResponse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .forms import CompanyForm, LinkForm, ProductForm
from .matching_review import matching_preview
from .models import (
    Company,
    Link,
    ParserSourceAttempt,
    Product,
    ProductMatchAlias,
    ProductMatchRule,
    ProductPriceHistory,
)
from .parser import parse_many_links_with_same_browser


@admin.register(ProductMatchRule)
class ProductMatchRuleAdmin(admin.ModelAdmin):
    list_display = ("word", "category", "purpose", "prefix", "active")
    list_filter = ("category", "purpose", "active", "prefix")
    list_editable = ("active",)
    search_fields = ("word",)


@admin.register(ProductMatchAlias)
class ProductMatchAliasAdmin(admin.ModelAdmin):
    list_display = ("name", "post", "active")
    list_filter = ("post__rubric", "active")
    autocomplete_fields = ("post",)
    search_fields = ("name", "post__title")
    list_editable = ("active",)


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
    list_display = (
        "name",
        "post",
        "match_status",
        "price",
        "price_updated_at",
        "last_seen_at",
        "consecutive_missing_count",
        "description",
        "auction_price",
        "currency",
        "active",
    )
    list_filter = ("match_status", "category", NullPostFilter, "active", "company")
    readonly_fields = ("match_reason",)
    actions = ["confirm_matches", "reassess_matches"]
    list_editable = ("post", "auction_price", "price", "currency", "active")
    search_fields = ("name", "description", "post__title", "source_product_key", "link")

    @admin.action(description="Підтвердити прив’язку або відсутність сорту для вибраних товарів")
    def confirm_matches(self, request, queryset):
        for product in queryset:
            product.match_status = Product.MatchStatus.CONFIRMED
            product.match_reason = "Адміністратор підтвердив прив’язку або відсутність сорту."
            product.save(update_fields=["match_status", "match_reason"])
            self.log_change(request, product, "Confirmed catalog matching decision")
        self.message_user(request, "Рішення підтверджені; наступні імпорти їх збережуть.")

    @admin.action(description="Перерахувати зіставлення — попередній перегляд", permissions=["change"])
    def reassess_matches(self, request, queryset):
        if not self.has_change_permission(request):
            raise PermissionDenied
        if queryset.count() > 200:
            self.message_user(request, "Виберіть не більше 200 товарів за один раз.", level=messages.WARNING)
            return None
        with transaction.atomic():
            products = list(queryset.select_for_update(of=("self",)).select_related("post").order_by("pk"))
            if any(not self.has_change_permission(request, product) for product in products):
                raise PermissionDenied
            rows = [matching_preview(product) for product in products]
            payload = {"user": request.user.pk, "rows": rows}
            if request.POST.get("apply_matching"):
                try:
                    approved = signing.loads(
                        request.POST.get("preview_token", ""), salt="companies.matching-preview", max_age=900
                    )
                except signing.BadSignature:
                    approved = None
                if approved != payload:
                    self.message_user(
                        request,
                        "Перегляд застарів або недійсний. Перевірте оновлений результат перед застосуванням.",
                        level=messages.WARNING,
                    )
                else:
                    changed = 0
                    for product, row in zip(products, rows, strict=True):
                        if not row["changed"]:
                            continue
                        # This is reassessment, not manual confirmation. Update only
                        # matching fields; Product.save would confirm a changed post.
                        Product.objects.filter(pk=product.pk).update(
                            post_id=row["post_id"], match_status=row["status"], match_reason=row["reason"]
                        )
                        self.log_change(
                            request,
                            product,
                            f"Перерахунок зіставлення: {row['old_post']} → {row['post']}. {row['reason']}",
                        )
                        changed += 1
                    self.message_user(request, f"Оновлено зіставлень: {changed}. Підтверджені рішення збережено.")
                    return None
            context = {
                **self.admin_site.each_context(request),
                "title": "Перегляд зіставлень товарів",
                "opts": self.model._meta,
                "rows": rows,
                "preview_token": signing.dumps(payload, salt="companies.matching-preview", compress=True),
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "has_changes": any(row["changed"] for row in rows),
            }
        return TemplateResponse(request, "admin/companies/matching_preview.html", context)

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
    readonly_fields = ("raw_data", "created")


@admin.register(ParserSourceAttempt)
class ParserSourceAttemptAdmin(admin.ModelAdmin):
    list_display = (
        "source_link",
        "worker_name",
        "status",
        "crawl_status",
        "product_count",
        "snapshot_complete",
        "parser_config_version",
        "created",
    )
    list_filter = ("status", "worker_name", "source_link")
    search_fields = ("source_link__url", "worker_name", "error")
    readonly_fields = ("parser_config", "created")
