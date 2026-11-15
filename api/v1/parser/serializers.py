import json
from datetime import timedelta
from math import ceil

from django.conf import settings
from django.db.models import F
from django.utils import timezone
from django.utils.translation import get_language
from lxml import etree, html
from rest_framework import serializers
from transliterate import slugify

from core.classifier.models import Category, Location
from core.companies.models import Company, CurrencyChoices, Link, ParserSourceAttempt, Product, ProductPriceHistory


class ParserConfigurationField(serializers.JSONField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not isinstance(value, dict):
            raise serializers.ValidationError("Parser configuration must be an object.")
        try:
            encoded = json.dumps(value, ensure_ascii=False).encode("utf-8")
        except UnicodeError as exc:
            raise serializers.ValidationError("Parser configuration contains invalid Unicode.") from exc
        if len(encoded) > settings.PARSER_MAX_CONFIG_BYTES:
            raise serializers.ValidationError("Parser configuration is too large.")
        for key, selector in value.items():
            if key == "snapshot_complete":
                if not isinstance(selector, bool):
                    raise serializers.ValidationError("snapshot_complete must be a boolean.")
            elif key == "max_pages":
                if type(selector) is not int or not 1 <= selector <= 50:
                    raise serializers.ValidationError("max_pages must be an integer between 1 and 50.")
            elif key == "encoding":
                try:
                    if not isinstance(selector, str) or not selector:
                        raise ValueError
                    html.HTMLParser(encoding=selector)
                except (LookupError, ValueError) as exc:
                    raise serializers.ValidationError("Unsupported page encoding.") from exc
            else:
                try:
                    if not isinstance(selector, str) or not selector.strip():
                        raise ValueError
                    etree.XPath(selector)
                except (ValueError, etree.XPathError) as exc:
                    raise serializers.ValidationError(f"Invalid XPath for {key}.") from exc
        return value


class ParserCatalogSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if isinstance(data, dict):
            invalid = set(data) - {name for name, field in self.fields.items() if not field.read_only}
            if invalid:
                raise serializers.ValidationError({name: "Unknown or read-only field." for name in invalid})
        return super().to_internal_value(data)


class ParserSourceSerializer(ParserCatalogSerializer):
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all())
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(source="category", queryset=Category.objects.all())
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    parser_map = ParserConfigurationField(required=False, allow_null=True)
    stored_parser_map = serializers.JSONField(source="parser_map", read_only=True)
    is_due = serializers.SerializerMethodField()
    lease_active = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["parser_map"] = instance.parser_map or instance.company.parser_map or {}
        return data

    def get_is_due(self, source):
        return source.is_due()

    def get_lease_active(self, source):
        return source.is_lease_active()

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
            "stored_parser_map",
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
            "active",
            "leased_by",
            "leased_until",
            "is_due",
            "lease_active",
        )
        read_only_fields = (
            "last_crawled",
            "last_crawl_status",
            "last_success_at",
            "last_error_at",
            "last_product_count",
            "leased_by",
            "leased_until",
        )
        extra_kwargs = {"crawl_interval_minutes": {"min_value": 1}}


class ParserSourceQuerySerializer(serializers.Serializer):
    after_id = serializers.IntegerField(min_value=0, required=False)
    category = serializers.CharField(required=False, allow_blank=True)
    experiment = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(min_value=1, max_value=100, default=20)
    scope = serializers.ChoiceField(choices=("due", "all"), default="due")
    company = serializers.IntegerField(min_value=1, required=False)
    active = serializers.BooleanField(required=False)


class LeaseSerializer(serializers.Serializer):
    worker_name = serializers.CharField(max_length=100, required=False)
    duration_minutes = serializers.IntegerField(min_value=1, max_value=240, default=30)
    force = serializers.BooleanField(default=False)


class LeaseResponseSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    leased_until = serializers.DateTimeField()


class ParserCompanySerializer(ParserCatalogSerializer):
    location_id = serializers.PrimaryKeyRelatedField(source="location", queryset=Location.objects.all())
    parser_map = ParserConfigurationField(required=False, allow_null=True)
    location_name = serializers.CharField(source="location.value", read_only=True)
    country_name = serializers.CharField(source="location.country.value", read_only=True)
    region_name = serializers.CharField(source="location.region.value", read_only=True)
    source_count = serializers.IntegerField(read_only=True, default=0)

    def validate(self, attrs):
        if not attrs.get("slug", self.instance.slug if self.instance else None):
            name = attrs.get("name", self.instance.name if self.instance else "")
            generated = slugify(name.lower(), get_language())
            if not generated:
                raise serializers.ValidationError({"slug": "Supply a non-empty unique slug for this company name."})
            try:
                attrs["slug"] = self.fields["slug"].run_validation(generated)
            except serializers.ValidationError as exc:
                raise serializers.ValidationError({"slug": exc.detail}) from exc
        return attrs

    class Meta:
        model = Company
        fields = (
            "id",
            "name",
            "slug",
            "type",
            "website",
            "active",
            "description",
            "location_id",
            "parser_map",
            "location_name",
            "country_name",
            "region_name",
            "latitude",
            "longitude",
            "source_count",
        )


class ParserCategorySerializer(serializers.ModelSerializer):
    parent_id = serializers.IntegerField(read_only=True)
    source_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ("id", "slug", "value", "parent_id", "is_active", "source_count")


class ParserSourceAttemptSerializer(serializers.ModelSerializer):
    source_url = serializers.CharField(source="source_link.url", read_only=True)

    class Meta:
        model = ParserSourceAttempt
        fields = (
            "id",
            "source_link_id",
            "source_url",
            "worker_name",
            "lease_token",
            "status",
            "crawl_status",
            "product_count",
            "error",
            "snapshot_complete",
            "parser_config_version",
            "parser_config",
            "created",
        )


class ParserProductSerializer(serializers.ModelSerializer):
    company_name = serializers.CharField(source="company.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)

    class Meta:
        model = Product
        fields = (
            "id",
            "source_link_id",
            "source_product_key",
            "post_id",
            "match_status",
            "match_reason",
            "company_id",
            "company_name",
            "category_id",
            "category_slug",
            "name",
            "description",
            "link",
            "active",
            "price",
            "min_price",
            "max_price",
            "currency",
            "price_updated_at",
            "last_seen_at",
            "consecutive_missing_count",
            "created",
        )


class ParserPriceHistorySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductPriceHistory
        fields = (
            "id",
            "product_id",
            "product_name",
            "source_link_id",
            "price",
            "min_price",
            "max_price",
            "currency",
            "observed_at",
            "raw_price",
            "worker_name",
            "created",
        )


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

    def validate_observed_at(self, value):
        future_limit = timezone.now() + timedelta(minutes=max(0, settings.PARSER_MAX_FUTURE_OBSERVATION_MINUTES))
        if value > future_limit:
            raise serializers.ValidationError("Observation timestamp is too far in the future.")
        return value

    def validate_raw(self, value):
        encoded = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > max(0, settings.PARSER_MAX_RAW_PRODUCT_BYTES):
            raise serializers.ValidationError("Raw product data is too large.")
        return value


class ParserResultsSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    worker_name = serializers.CharField(max_length=100, required=False)
    products = ParsedProductSerializer(many=True)
    snapshot_complete = serializers.BooleanField(default=False)
    parser_config_version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    parser_config = serializers.JSONField(required=False)

    def validate_parser_config(self, value):
        encoded = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > max(0, settings.PARSER_MAX_CONFIG_BYTES):
            raise serializers.ValidationError("Parser configuration snapshot is too large.")
        return value

    def validate_products(self, products):
        if len(products) > max(1, settings.PARSER_MAX_PRODUCTS_PER_RESULT):
            raise serializers.ValidationError("Too many products in one parser result.")
        keys = []
        for item in products:
            product_url = item.get("product_url") or ""
            keys.append(product_url or item["name"].strip().casefold())
        if len(keys) != len(set(keys)):
            raise serializers.ValidationError("Parser result contains duplicate product identities.")
        return products

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs["snapshot_complete"]:
            return attrs

        product_count = len(attrs["products"])
        if product_count == 0:
            raise serializers.ValidationError({"snapshot_complete": "A complete snapshot cannot be empty."})

        active_product_count = Product.objects.filter(
            source_link=self.context["source"],
            active=True,
        ).count()
        ratio = min(1.0, max(0.0, settings.PARSER_MIN_COMPLETE_SNAPSHOT_RATIO))
        minimum_expected = ceil(active_product_count * ratio)
        if active_product_count and product_count < minimum_expected:
            raise serializers.ValidationError(
                {
                    "snapshot_complete": (
                        f"Complete snapshot contains {product_count} products; at least "
                        f"{minimum_expected} are required for {active_product_count} active products."
                    )
                }
            )
        return attrs

    def save(self, **kwargs):
        source = self.context["source"]
        worker_name = self.context["worker_name"]
        now = timezone.now()
        products = []
        seen_product_ids = []

        for item in self.validated_data["products"]:
            observed_at = item.get("observed_at") or now
            product_url = item.get("product_url") or ""
            source_product_key = product_url or item["name"].strip().casefold()
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
                "last_seen_at": now,
                "consecutive_missing_count": 0,
            }
            existing = Product.objects.filter(
                source_link=source,
                source_product_key=source_product_key,
            ).first()
            should_update_current_price = has_price_data and (
                existing is None or existing.price_updated_at is None or observed_at >= existing.price_updated_at
            )
            if should_update_current_price:
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
            seen_product_ids.append(product.pk)

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
                    raw_data=item.get("raw"),
                    worker_name=worker_name,
                )

        snapshot_complete = self.validated_data["snapshot_complete"]
        if snapshot_complete:
            missing_products = Product.objects.filter(source_link=source).exclude(pk__in=seen_product_ids)
            missing_products.update(consecutive_missing_count=F("consecutive_missing_count") + 1)
            threshold = max(1, settings.PARSER_MISSING_DEACTIVATION_THRESHOLD)
            missing_products.filter(consecutive_missing_count__gte=threshold).update(active=False)

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
            snapshot_complete=snapshot_complete,
            parser_config_version=self.validated_data.get("parser_config_version", source.parser_config_version),
            parser_config=self.validated_data.get(
                "parser_config", source.parser_map or source.company.parser_map or {}
            ),
        )
        return products


class ParserFailureSerializer(serializers.Serializer):
    lease_token = serializers.UUIDField()
    worker_name = serializers.CharField(max_length=100, required=False)
    status = serializers.IntegerField(required=False, allow_null=True)
    error = serializers.CharField(allow_blank=True)
    parser_config_version = serializers.CharField(max_length=64, required=False, allow_blank=True)
    parser_config = serializers.JSONField(required=False)

    def validate_parser_config(self, value):
        encoded = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        if len(encoded) > max(0, settings.PARSER_MAX_CONFIG_BYTES):
            raise serializers.ValidationError("Parser configuration snapshot is too large.")
        return value
