"""Permission-scoped taxonomy and category SEO management."""

from django.conf import settings
from django.contrib.admin.models import ADDITION, CHANGE
from django.core.exceptions import ValidationError as ModelValidationError
from django.db import connection
from django.db.models import Q
from django.urls import get_resolver, reverse
from django.urls.resolvers import LocalePrefixPattern
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.validators import UniqueValidator

from core.classifier.models import Category, CategoryHub, CategoryHubSection, CategoryURLRedirect
from core.posts.models import Post
from core.services.models import MetaData

from .management import CropSetupAccess, audit
from .views import ContentPagination


def lock_taxonomy():
    # MPTT moves update siblings and descendants, including across tree roots.
    with connection.cursor() as cursor:
        cursor.execute("LOCK TABLE classifier_category IN SHARE ROW EXCLUSIVE MODE")


def reserved_slugs():
    def collect(patterns):
        result = set()
        for pattern in patterns:
            if isinstance(pattern.pattern, LocalePrefixPattern):
                result.update(collect(pattern.url_patterns))
                continue
            route = str(pattern.pattern)
            first = route.split("/", 1)[0]
            if first and "<" not in first and not route.startswith("^"):
                result.add(first)
            elif not route and hasattr(pattern, "url_patterns"):
                result.update(collect(pattern.url_patterns))
        return result

    return (
        collect(get_resolver().url_patterns)
        | {"forum", "static", "media", "api"}
        | {language for language, _ in settings.LANGUAGES}
    )


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - {key for key, field in self.fields.items() if not field.read_only}
            if unknown:
                raise serializers.ValidationError({key: "Unknown or read-only field." for key in unknown})
        return super().to_internal_value(data)


class CategorySEOSerializer(StrictFieldsMixin, serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(max_length=255, required=False)
    h1 = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    text = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=200000)


class CategorySetupSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=250, validators=[UniqueValidator(queryset=Category.objects.all())])
    seo = CategorySEOSerializer(source="meta", required=False, allow_null=True)
    url = serializers.CharField(source="absolute_url", read_only=True)

    def validate_slug(self, value):
        if value in reserved_slugs() and (not self.instance or self.instance.slug != value):
            raise serializers.ValidationError("This slug is reserved for an application route.")
        return value

    def validate(self, attrs):
        parent = attrs.get("parent", self.instance.parent if self.instance else None)
        structural = not self.instance or any(
            name in attrs and attrs[name] != getattr(self.instance, name) for name in ("parent", "slug")
        )
        if structural:
            if self.instance and parent and (parent.pk == self.instance.pk or parent.is_descendant_of(self.instance)):
                raise serializers.ValidationError({"parent": "A category cannot be moved into its own subtree."})
            level = parent.level + 1 if parent else 0
            height = 0
            if self.instance:
                levels = self.instance.get_descendants(include_self=True).values_list("level", flat=True)
                height = max(levels) - self.instance.level
            if level + height > 2:
                raise serializers.ValidationError(
                    {"parent": "Public category routes support root, crop and catalog levels only."}
                )
            if self.instance and level == 0 and Post.objects.filter(rubric=self.instance).exists():
                raise serializers.ValidationError({"parent": "A structural root cannot own articles."})
        return attrs

    class Meta:
        model = Category
        fields = ("id", "slug", "value", "parent", "is_active", "presentation_mode", "seo", "url", "level")
        read_only_fields = ("level",)


def save_category(serializer, request):
    creating = serializer.instance is None
    data = dict(serializer.validated_data)
    seo_present = "meta" in data
    seo = data.pop("meta", None)
    category = serializer.instance or Category()
    structural = creating or any(key in data and data[key] != getattr(category, key) for key in ("parent", "slug"))
    old_urls = (
        dict(category.get_descendants(include_self=True).values_list("pk", "absolute_url")) if not creating else {}
    )
    for key, value in data.items():
        setattr(category, key, value)
    if seo_present:
        if seo is None:
            category.meta = None
        else:
            # Never mutate metadata potentially shared with another domain object.
            values = {key: getattr(category.meta, key, "") for key in ("title", "description", "h1", "text")}
            values.update(seo)
            for key in ("title", "description"):
                values[key] = values[key] or category.value
            if category.meta is None or any(getattr(category.meta, key) != value for key, value in values.items()):
                category.meta = MetaData.objects.create(**values)
    if structural:
        # Invoke MPTT, bypassing Category.save's unrelated image rewrite.
        super(Category, category).save()
        category.refresh_from_db()
        affected = list(category.get_descendants(include_self=True))
        for node in affected:
            node.absolute_url = node.get_absolute_url()
            if len(node.absolute_url) > 1000:
                raise serializers.ValidationError("Category URL is too long.")
            if node.level:
                conflict = CategoryURLRedirect.objects.filter(old_path=node.absolute_url).exclude(category=node)
                if conflict.exists():
                    raise serializers.ValidationError("This public path is reserved by a previous category URL.")
                CategoryURLRedirect.objects.filter(old_path=node.absolute_url, category=node).delete()
        Category.objects.bulk_update(affected, ["absolute_url"])
        for node in affected:
            previous = old_urls.get(node.pk)
            if previous and previous != "/" and previous != node.absolute_url:
                CategoryURLRedirect.objects.update_or_create(old_path=previous, defaults={"category": node})
        # Post routes resolve by ID and redirect mismatched paths to this stored URL.
        posts = list(Post.objects.filter(rubric_id__in=[node.pk for node in affected]).select_related("rubric__parent"))
        for post in posts:
            if not post.rubric.parent_id:
                raise serializers.ValidationError("A structural root cannot own articles.")
            post.absolute_url = reverse(
                "post-detail", args=(post.rubric.parent.slug, post.rubric.slug, post.slug, post.pk)
            )
            if len(post.absolute_url) > 512:
                raise serializers.ValidationError("Moving this category would exceed an article URL limit.")
        Post.objects.bulk_update(posts, ["absolute_url"])
        affected_ids = [node.pk for node in affected]
        hubs = CategoryHub.objects.filter(Q(category_id__in=affected_ids) | Q(guide_category_id__in=affected_ids))
        sections = CategoryHubSection.objects.filter(
            Q(hub__category_id__in=affected_ids) | Q(category_id__in=affected_ids)
        )
        try:
            for reference in list(hubs) + list(sections):
                reference.full_clean()
        except ModelValidationError as exc:
            raise serializers.ValidationError(getattr(exc, "message_dict", exc.messages)) from exc
    else:
        fields = {key: getattr(category, key) for key in data}
        if seo_present:
            fields["meta"] = category.meta
        if fields:
            Category.objects.filter(pk=category.pk).update(**fields)
    category.refresh_from_db()
    CategoryHub.objects.update(updated=timezone.now())
    audit(request, category, ADDITION if creating else CHANGE, serializer.validated_data)
    serializer.instance = category


class CategorySetupList(CropSetupAccess, ListCreateAPIView):
    queryset = Category.objects.select_related("meta", "parent").order_by("tree_id", "lft")
    serializer_class = CategorySetupSerializer
    pagination_class = ContentPagination

    def get_queryset(self):
        queryset = super().get_queryset()
        parent = self.request.query_params.get("parent")
        if parent == "null":
            queryset = queryset.filter(parent__isnull=True)
        elif parent is not None:
            if not parent.isascii() or not parent.isdecimal() or int(parent) < 1:
                raise serializers.ValidationError({"parent": "Use a positive ID or null."})
            queryset = queryset.filter(parent_id=int(parent))
        active = self.request.query_params.get("is_active")
        if active is not None:
            if active not in ("true", "false"):
                raise serializers.ValidationError({"is_active": "Use true or false."})
            queryset = queryset.filter(is_active=active == "true")
        slug = self.request.query_params.get("slug")
        return queryset.filter(slug=slug) if slug else queryset

    def create(self, request, *args, **kwargs):
        def perform():
            lock_taxonomy()
            return super(CategorySetupList, self).create(request, *args, **kwargs)

        return self.mutate(perform)

    def perform_create(self, serializer):
        save_category(serializer, self.request)


class CategorySetupDetail(CropSetupAccess, RetrieveUpdateAPIView):
    queryset = Category.objects.select_related("meta", "parent")
    serializer_class = CategorySetupSerializer
    http_method_names = ("get", "patch", "head", "options")

    def update(self, request, *args, **kwargs):
        def perform():
            lock_taxonomy()
            return super(CategorySetupDetail, self).update(request, *args, **kwargs)

        return self.mutate(perform)

    def perform_update(self, serializer):
        save_category(serializer, self.request)
