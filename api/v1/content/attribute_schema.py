"""Token-authenticated schema discovery and permission-protected
maintenance."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from core.classifier.models import Category
from core.posts.models import CategoryAttributeChoice, CategoryAttributeField, CategoryAttributeGroup, Post

from .views import ContentPagination, ContentTokenMixin


class SchemaPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            return True
        model = view.queryset.model
        action = "add" if request.method == "POST" else "change"
        return request.user.is_staff and request.user.has_perm(f"posts.{action}_{model._meta.model_name}")


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryAttributeGroup
        fields = ("id", "category", "title", "description", "is_active", "sort_order")

    def validate(self, attrs):
        if self.instance and attrs.get("category", self.instance.category) != self.instance.category:
            raise serializers.ValidationError("Group category cannot change; create a new group.")
        return attrs


class FieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryAttributeField
        fields = (
            "id",
            "category",
            "group",
            "key",
            "label",
            "field_type",
            "help_text",
            "unit",
            "decimal_places",
            "min_value",
            "max_value",
            "is_active",
            "is_required",
            "is_filterable",
            "is_public",
            "sort_order",
        )

    def validate(self, attrs):
        category = attrs.get("category") or getattr(self.instance, "category", None)
        group = attrs.get("group", getattr(self.instance, "group", None))
        if group and group.category_id != category.pk:
            raise serializers.ValidationError("Group must belong to the same category.")
        if attrs.get("decimal_places", getattr(self.instance, "decimal_places", 0)) > 4:
            raise serializers.ValidationError("Filter index supports at most four decimal places.")
        low = attrs.get("min_value", getattr(self.instance, "min_value", None))
        high = attrs.get("max_value", getattr(self.instance, "max_value", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError("Minimum exceeds maximum.")
        if self.instance:
            used = self.instance.post_values.exists()
            semantics = (
                "category",
                "key",
                "field_type",
                "unit",
                "decimal_places",
                "min_value",
                "max_value",
                "is_required",
                "is_filterable",
            )
            if not used and any(k in attrs and attrs[k] != getattr(self.instance, k) for k in semantics):
                stored = Post.objects.filter(category_attributes__has_key=str(self.instance.category_id)).values_list(
                    "category_attributes", flat=True
                )
                used = any(
                    self.instance.key in (row.get(str(self.instance.category_id)) or {}) for row in stored.iterator()
                )
            for key in (
                "category",
                "key",
                "field_type",
                "unit",
                "decimal_places",
                "min_value",
                "max_value",
                "is_required",
            ):
                if key in attrs and attrs[key] != getattr(self.instance, key) and used:
                    raise serializers.ValidationError(
                        "Used field semantics cannot change; create a new field and migrate explicitly."
                    )
            if used and attrs.get("is_filterable") is True and not self.instance.is_filterable:
                raise serializers.ValidationError(
                    "Existing values require an explicit index rebuild before enabling filtering."
                )
        return attrs


class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryAttributeChoice
        fields = ("id", "field", "value", "label", "is_active", "is_public", "sort_order")

    def validate(self, attrs):
        if self.instance and any(k in attrs and attrs[k] != getattr(self.instance, k) for k in ("field", "value")):
            raise serializers.ValidationError("Choice identity cannot change; create a new choice.")
        return attrs


class CategorySchemaView(ContentTokenMixin, APIView):
    def get(self, request, pk):
        category = get_object_or_404(Category, pk=pk, is_active=True)
        fields = category.attribute_fields.select_related("group").prefetch_related("choices").order_by("pk")
        rows = []
        for field in fields:
            row = dict(FieldSerializer(field).data)
            row["choices"] = ChoiceSerializer(field.choices.all(), many=True).data
            rows.append(row)
        import hashlib
        import json

        schema = {
            "category_id": category.pk,
            "groups": GroupSerializer(category.attribute_groups.all(), many=True).data,
            "fields": rows,
        }
        schema["checksum"] = hashlib.sha256(json.dumps(schema, sort_keys=True, default=str).encode()).hexdigest()
        return Response(schema)


class SchemaWriteMixin(ContentTokenMixin):
    permission_classes = (SchemaPermission,)
    pagination_class = ContentPagination
    http_method_names = ("get", "post", "put", "patch", "head", "options")

    def get_queryset(self):
        queryset = self.queryset.all()
        for key in ("category", "field"):
            if key in self.request.query_params and key in {f.name for f in queryset.model._meta.fields}:
                queryset = queryset.filter(**{key: self.request.query_params[key]})
        return queryset.order_by("pk")

    @transaction.atomic
    def perform_create(self, serializer):
        category = serializer.validated_data.get("category")
        if category is None:
            category = serializer.validated_data["field"].category
        Category.objects.select_for_update().get(pk=category.pk)
        serializer.validated_data.update(serializer.validate(dict(serializer.validated_data)))
        serializer.save()

    @transaction.atomic
    def perform_update(self, serializer):
        category = getattr(serializer.instance, "category", None)
        if category is None:
            category = serializer.instance.field.category
        Category.objects.select_for_update().get(pk=category.pk)
        serializer.instance = self.queryset.select_for_update().get(pk=serializer.instance.pk)
        serializer.validated_data.update(serializer.validate(dict(serializer.validated_data)))
        serializer.save()


class GroupListView(SchemaWriteMixin, ListCreateAPIView):
    queryset = CategoryAttributeGroup.objects.all()
    serializer_class = GroupSerializer


class GroupDetailView(SchemaWriteMixin, RetrieveUpdateAPIView):
    queryset = CategoryAttributeGroup.objects.all()
    serializer_class = GroupSerializer


class FieldListView(SchemaWriteMixin, ListCreateAPIView):
    queryset = CategoryAttributeField.objects.all()
    serializer_class = FieldSerializer


class FieldDetailView(SchemaWriteMixin, RetrieveUpdateAPIView):
    queryset = CategoryAttributeField.objects.all()
    serializer_class = FieldSerializer


class ChoiceListView(SchemaWriteMixin, ListCreateAPIView):
    queryset = CategoryAttributeChoice.objects.all()
    serializer_class = ChoiceSerializer


class ChoiceDetailView(SchemaWriteMixin, RetrieveUpdateAPIView):
    queryset = CategoryAttributeChoice.objects.all()
    serializer_class = ChoiceSerializer
