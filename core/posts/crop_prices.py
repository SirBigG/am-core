"""Nominal offer ranges, with daily recorded observations for the current
cohort."""

from datetime import timedelta
from decimal import Decimal
from statistics import median

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


def current_price_ranges(products):
    return list(
        _ranges(products)
        .annotate(
            offer_count=Count("pk"), seller_count=Count("company_id", distinct=True), updated_at=Max("price_updated_at")
        )
        .order_by("currency_code")
    )


def build_price_overview(offers, now, days=30):
    # A subquery preserves the legacy window/deduplication filter before GROUP BY.
    products = Product.objects.filter(pk__in=offers.values("pk"))
    current = current_price_ranges(products)
    if not current:
        return []
    today = timezone.localtime(now).date()
    start = today - timedelta(days=days - 1)
    history = (
        ProductPriceHistory.objects.filter(
            product_id__in=products.values("pk"), observed_at__date__gte=start, observed_at__lte=now
        )
        .filter(Q(price__gt=0) | Q(price__isnull=True, min_price__gt=0))
        .annotate(day=TruncDate("observed_at"))
    )
    daily = list(_ranges(history, "day").annotate(offer_count=Count("product_id", distinct=True)).order_by("day"))
    seller_prices = {}
    observations = history.order_by("observed_at", "pk").values(
        "day", "currency", "price", "min_price", "max_price", "product__company_id"
    )
    for observation in observations:
        key = (observation["currency"] or "", observation["day"])
        lower = observation["price"] if observation["price"] is not None else observation["min_price"]
        upper = lower if observation["price"] is not None else max(lower, observation["max_price"] or lower)
        seller_prices.setdefault(key, {})[observation["product__company_id"]] = (lower + upper) / Decimal(2)
    labels = dict(CurrencyChoices.choices)
    for group in current:
        code = group["currency_code"]
        group["currency"] = labels.get(code, code) or "Валюта не вказана"
        rows = [row for row in daily if row["currency_code"] == code]
        group["history"] = rows
        group["has_chart"] = len(rows) >= 2
        group["chart_max"] = max((row["max"] for row in rows), default=0)
        for row in rows:
            row["x"] = 20 + (row["day"] - start).days * 580 // (days - 1)
            row["y_min"] = 160 - int(row["min"] / group["chart_max"] * 140)
            row["y_max"] = 160 - int(row["max"] / group["chart_max"] * 140)
        for row in rows:
            prices = seller_prices[(code, row["day"])]
            row["median"] = median(prices.values())
            row["seller_count"] = len(prices)
            row["chart_x"] = 80 + (row["day"] - start).days * 500 // (days - 1)
            row["chart_low"] = 180 - int(row["min"] / group["chart_max"] * 150)
            row["chart_high"] = 180 - int(row["max"] / group["chart_max"] * 150)
            row["chart_median"] = 180 - int(row["median"] / group["chart_max"] * 150)
        group["median_points"] = " ".join(f'{row["chart_x"]},{row["chart_median"]}' for row in rows)
        group["range_points"] = " ".join(
            [f'{row["chart_x"]},{row["chart_high"]}' for row in rows]
            + [f'{row["chart_x"]},{row["chart_low"]}' for row in reversed(rows)]
        )
        group["chart_ticks"] = [
            {"y": 30, "value": group["chart_max"]},
            {"y": 105, "value": group["chart_max"] / 2},
            {"y": 180, "value": 0},
        ]
        group["start"] = start
        group["end"] = today
    return current
