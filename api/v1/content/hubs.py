"""Token-only, permission-scoped management of existing hub references."""

from django.contrib import admin
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import IntegrityError, transaction
from django.utils.cache import add_never_cache_headers
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.generics import RetrieveUpdateAPIView, get_object_or_404
from rest_framework.permissions import DjangoModelPermissions, IsAdminUser
from rest_framework.viewsets import ModelViewSet

from core.classifier.models import Category, CategoryHub, CategoryHubSection
from core.posts.guide_admin_permissions import require_guide_placement_deletion
from core.posts.models import GuideSection, GuideSectionArticle, Post

from .views import ContentPagination, ContentTokenMixin


class HubPermissions(DjangoModelPermissions):
    perms_map = {
        **DjangoModelPermissions.perms_map,
        "GET": ["%(app_label)s.view_%(model_name)s"],
        "HEAD": ["%(app_label)s.view_%(model_name)s"],
        "OPTIONS": ["%(app_label)s.view_%(model_name)s"],
    }


def visible_posts(request):
    return admin.site.get_model_admin(Post).get_queryset(request)


class ValidatedReferenceSerializer(serializers.ModelSerializer):
    """Same model validation as admin, including partial-update state."""

    parent_field = None

    def validate(self, attrs):
        if self.instance and self.parent_field in attrs:
            if attrs[self.parent_field].pk != getattr(self.instance, f"{self.parent_field}_id"):
                raise serializers.ValidationError({self.parent_field: "Parent cannot change; create a new reference."})
        instance = self.Meta.model()
        if self.instance:
            for field in self.Meta.model._meta.concrete_fields:
                setattr(instance, field.attname, getattr(self.instance, field.attname))
            instance._state.adding = False
        for field, value in attrs.items():
            setattr(instance, field, value)
        try:
            # generated updated timestamps are deliberately read-only
            instance.full_clean(exclude=["updated"] if hasattr(instance, "updated") else [])
        except ModelValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
        return attrs

    def _lock_parent(self, attrs):
        parent = attrs.get(self.parent_field) or getattr(self.instance, self.parent_field, None)
        if parent is not None:
            get_object_or_404(type(parent).objects.select_for_update(), pk=parent.pk)

    def create(self, validated_data):
        self._lock_parent(validated_data)
        self.validate(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        self._lock_parent(validated_data)
        self.validate(validated_data)
        return super().update(instance, validated_data)


class HubSerializer(ValidatedReferenceSerializer):
    parent_field = "category"
    url = serializers.CharField(source="category.absolute_url", read_only=True)

    class Meta:
        model = CategoryHub
        fields = ("id", "category", "is_active", "description", "guide_category", "site", "locale", "updated", "url")
        read_only_fields = ("updated",)


class HubSectionSerializer(ValidatedReferenceSerializer):
    parent_field = "hub"
    url = serializers.CharField(source="category.absolute_url", read_only=True)

    class Meta:
        model = CategoryHubSection
        fields = ("id", "hub", "category", "role", "title", "description", "sort_order", "is_active", "url")


class GuideSectionSerializer(ValidatedReferenceSerializer):
    parent_field = "category"

    class Meta:
        model = GuideSection
        fields = ("id", "category", "title", "description", "sort_order", "is_active")


class GuidePlacementSerializer(ValidatedReferenceSerializer):
    parent_field = "section"
    title = serializers.CharField(source="post.title", read_only=True)
    url = serializers.CharField(source="post.absolute_url", read_only=True)

    class Meta:
        model = GuideSectionArticle
        fields = ("id", "section", "post", "sort_order", "title", "url")

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get("request")
        fields["post"].queryset = visible_posts(request) if request else Post.objects.none()
        return fields


class PrivateHubAccess(ContentTokenMixin):
    permission_classes = (IsAdminUser, HubPermissions)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        add_never_cache_headers(response)
        return response


class ReferenceViewSet(PrivateHubAccess, ModelViewSet):
    pagination_class = ContentPagination
    filter_field = None
    http_method_names = ("get", "post", "put", "patch", "delete", "head", "options")

    def get_queryset(self):
        queryset = super().get_queryset()
        value = self.request.query_params.get(self.filter_field) if self.filter_field else None
        if value is not None:
            if not value.isascii() or not value.isdecimal() or int(value) < 1:
                raise ValidationError({self.filter_field: "Use a positive integer ID."})
            queryset = queryset.filter(**{f"{self.filter_field}_id": int(value)})
        return queryset

    def get_object(self):
        if self.request.method not in ("GET", "HEAD", "OPTIONS"):
            # Lock configuration parents before children, matching creation and
            # cascade deletion. Do not lock unrelated joined category/Post rows.
            instance = super().get_object()
            parent_field = self.serializer_class.parent_field
            parent = getattr(instance, parent_field)
            if isinstance(parent, (CategoryHub, GuideSection)):
                get_object_or_404(type(parent).objects.select_for_update(), pk=parent.pk)
            self.queryset = self.queryset.select_for_update(of=("self",))
        return super().get_object()

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().create(request, *args, **kwargs)
        except IntegrityError as exc:
            raise ValidationError("Conflicting reference; read current configuration and retry.") from exc

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                return super().update(request, *args, **kwargs)
        except IntegrityError as exc:
            raise ValidationError("Conflicting reference; read current configuration and retry.") from exc

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class HubViewSet(ReferenceViewSet):
    queryset = CategoryHub.objects.select_related("category").order_by("pk")
    serializer_class = HubSerializer
    filter_field = "category"

    def perform_destroy(self, instance):
        if instance.sections.exists() and not self.request.user.has_perm("classifier.delete_categoryhubsection"):
            raise PermissionDenied("Deleting a populated hub also requires section delete permission.")
        super().perform_destroy(instance)


class HubSectionViewSet(ReferenceViewSet):
    queryset = CategoryHubSection.objects.select_related("category", "hub").order_by("sort_order", "pk")
    serializer_class = HubSectionSerializer
    filter_field = "hub"


class GuideSectionViewSet(ReferenceViewSet):
    queryset = GuideSection.objects.order_by("sort_order", "pk")
    serializer_class = GuideSectionSerializer
    filter_field = "category"

    def perform_destroy(self, instance):
        require_guide_placement_deletion(admin.site, self.request, instance.articles.all())
        super().perform_destroy(instance)


class GuidePlacementViewSet(ReferenceViewSet):
    queryset = GuideSectionArticle.objects.select_related("post", "section").order_by("sort_order", "pk")
    serializer_class = GuidePlacementSerializer
    filter_field = "section"

    def get_queryset(self):
        return super().get_queryset().filter(post__in=visible_posts(self.request))


class PresentationSerializer(serializers.ModelSerializer):
    url = serializers.CharField(source="absolute_url", read_only=True)

    class Meta:
        model = Category
        fields = ("id", "slug", "value", "presentation_mode", "url")
        read_only_fields = ("slug", "value")

    def update(self, instance, validated_data):
        # Category.save() regenerates URLs and may rewrite images. This API only
        # changes presentation; preserve every existing taxonomy/SEO field.
        if "presentation_mode" in validated_data:
            Category.objects.filter(pk=instance.pk).update(presentation_mode=validated_data["presentation_mode"])
            instance.presentation_mode = validated_data["presentation_mode"]
        return instance


class CategoryPresentationView(PrivateHubAccess, RetrieveUpdateAPIView):
    queryset = Category.objects.all()
    serializer_class = PresentationSerializer
    http_method_names = ("get", "patch", "head", "options")
