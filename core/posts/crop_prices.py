"""Nominal offer ranges, with daily recorded observations for the current
cohort."""

from datetime import timedelta

from django.db.models import Case, Count, F, Max, Min, Q, Value, When
from django.db.models.functions import Coalesce, Greatest, NullIf, TruncDate
from django.utils import timezone

from core.companies.models import CurrencyChoices, Product, ProductPriceHistory


def _ranges(queryset, *dimensions):
    lower = Coalesce("price", "min_price")
    upper = Case(
        When(price__isnull=False, then=F("price")),
        default=Greatest(F("min_price"), Coalesce("max_price", "min_price")),
    )
    return (
        queryset.order_by()
        .annotate(currency_code=Coalesce(NullIf("currency", Value("")), Value("")))
        .values("currency_code", *dimensions)
        .annotate(min=Min(lower), max=Max(upper))
    )


def build_price_overview(offers, now):
    # A subquery preserves the legacy window/deduplication filter before GROUP BY.
    products = Product.objects.filter(pk__in=offers.values("pk"))
    current = list(
        _ranges(products)
        .annotate(
            offer_count=Count("pk"), seller_count=Count("company_id", distinct=True), updated_at=Max("price_updated_at")
        )
        .order_by("currency_code")
    )
    if not current:
        return []
    today = timezone.localtime(now).date()
    start = today - timedelta(days=29)
    history = (
        ProductPriceHistory.objects.filter(
            product_id__in=products.values("pk"), observed_at__date__gte=start, observed_at__lte=now
        )
        .filter(Q(price__gt=0) | Q(price__isnull=True, min_price__gt=0))
        .annotate(day=TruncDate("observed_at"))
    )
    daily = list(_ranges(history, "day").annotate(offer_count=Count("product_id", distinct=True)).order_by("day"))
    labels = dict(CurrencyChoices.choices)
    for group in current:
        code = group["currency_code"]
        group["currency"] = labels.get(code, code) or "Валюта не вказана"
        rows = [row for row in daily if row["currency_code"] == code]
        group["history"] = rows
        group["has_chart"] = len(rows) >= 2
        group["chart_max"] = max((row["max"] for row in rows), default=0)
        for row in rows:
            row["x"] = 20 + (row["day"] - start).days * 20
            row["y_min"] = 160 - int(row["min"] / group["chart_max"] * 140)
            row["y_max"] = 160 - int(row["max"] / group["chart_max"] * 140)
        group["start"] = start
        group["end"] = today
    return current
