from django.utils import timezone
from rest_framework import serializers

from core.companies.models import CurrencyChoices, Link, ParserSourceAttempt, Product, ProductPriceHistory


class ParserSourceSerializer(serializers.ModelSerializer):
    company_id = serializers.IntegerField(read_only=True)
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_id = serializers.IntegerField(read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Link
        fields = (
            "id",
            "url",
            "company_id",
            "company_name",
            "category_id",
            "category_slug",
            "parser_map",
            "source_type",
            "experiment_label",
            "parser_config_version",
            "priority",
            "crawl_interval_minutes",
            "last_crawled",
            "last_crawl_status",
            "last_success_at",
            "last_error_at",
            "last_product_count",
        )


class ParserSourceQuerySerializer(serializers.Serializer):
    category = serializers.CharField(required=False, allow_blank=True)
    experiment = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)


class LeaseSerializer(serializers.Serializer):
    worker_name = serializers.CharField(max_length=100, required=False)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=240, default=30)


class LeaseResponseSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    leased_until = serializers.DateTimeField()


class ParsedProductSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    product_url = serializers.URLField(required=False, allow_blank=True, allow_null=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    currency = serializers.ChoiceField(choices=CurrencyChoices.choices, default=CurrencyChoices.UAH)
    observed_at = serializers.DateTimeField(required=False)
    raw_price = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    raw = serializers.JSONField(required=False)


class ParserResultsSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    worker_name = serializers.CharField(max_length=100, required=False)
    products = ParsedProductSerializer(many=True)

    def save(self, **kwargs):
        source = self.context["source"]
        worker_name = self.validated_data.get("worker_name") or self.context["worker_name"]
        now = timezone.now()
        products = []

        for item in self.validated_data["products"]:
            observed_at = item.get("observed_at") or now
            product_url = item.get("product_url") or ""
            source_product_key = product_url or item["name"].strip().lower()
            has_price_data = any(item.get(field) is not None for field in ("price", "min_price", "max_price"))
            defaults = {
                "company_id": source.company_id,
                "category_id": source.category_id,
                "source_link": source,
                "source_product_key": source_product_key,
                "name": item["name"],
                "description": item.get("description") or "",
                "link": product_url or None,
                "active": True,
            }
            if has_price_data:
                defaults.update(
                    {
                        "price": item.get("price"),
                        "min_price": item.get("min_price"),
                        "max_price": item.get("max_price"),
                        "currency": item.get("currency") or CurrencyChoices.UAH,
                        "price_updated_at": observed_at,
                    }
                )
            product, _created = Product.objects.update_or_create(
                source_link=source,
                source_product_key=source_product_key,
                defaults=defaults,
            )
            products.append(product)

            if has_price_data:
                ProductPriceHistory.objects.create(
                    product=product,
                    source_link=source,
                    price=item.get("price"),
                    min_price=item.get("min_price"),
                    max_price=item.get("max_price"),
                    currency=item.get("currency") or CurrencyChoices.UAH,
                    observed_at=observed_at,
                    raw_price=item.get("raw_price") or "",
                    worker_name=worker_name,
                )

        source.last_crawled = now
        source.last_success_at = now
        source.last_crawl_status = 200
        source.last_error = ""
        source.last_product_count = len(products)
        source.leased_by = None
        source.lease_token = None
        source.leased_until = None
        source.save(
            update_fields=[
                "last_crawled",
                "last_success_at",
                "last_crawl_status",
                "last_error",
                "last_product_count",
                "leased_by",
                "lease_token",
                "leased_until",
            ]
        )
        ParserSourceAttempt.objects.create(
            source_link=source,
            worker_name=worker_name,
            lease_token=self.validated_data["lease_token"],
            status=ParserSourceAttempt.STATUS_SUCCESS,
            crawl_status=source.last_crawl_status,
            product_count=len(products),
        )
        return products


class ParserFailureSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    worker_name = serializers.CharField(max_length=100, required=False)
    status = serializers.IntegerField(required=False, allow_null=True)
    error = serializers.CharField(allow_blank=True)
