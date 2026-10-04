from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from core.classifier.models import Category, Country
from core.posts.attribute_validation import validate_category_attributes
from core.posts.category_attributes import rebuild_post_attribute_values
from core.posts.metadata import resolve_publication_metadata
from core.posts.models import Photo, Post


class CategoryTreeSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(source="value", read_only=True)
    children = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ("id", "slug", "title", "children")

    def get_children(self, instance):
        children = instance.get_children().filter(is_active=True).order_by("tree_id", "lft")
        return CategoryTreeSerializer(children, many=True).data


class CountrySerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(source="value", read_only=True)

    class Meta:
        model = Country
        fields = ("id", "slug", "short_slug", "title")


class PostPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Photo
        fields = ("id", "image", "description", "author", "source")


class PostCategorySerializer(serializers.ModelSerializer):
    title = serializers.CharField(source="value", read_only=True)

    class Meta:
        model = Category
        fields = ("id", "slug", "title")


class PostCountrySerializer(CountrySerializer):
    pass


class ContentPostSerializer(serializers.ModelSerializer):
    publisher = serializers.PrimaryKeyRelatedField(read_only=True)
    rubric = serializers.PrimaryKeyRelatedField(queryset=Category.objects.filter(is_active=True))
    country = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), allow_null=True, required=False)
    photos = PostPhotoSerializer(source="photo", many=True, read_only=True)
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    url = serializers.CharField(source="absolute_url", read_only=True)
    resolved_metadata = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = (
            "id",
            "title",
            "text",
            "slug",
            "work_status",
            "author",
            "source",
            "sources",
            "publisher",
            "publish_date",
            "update_date",
            "hits",
            "status",
            "rubric",
            "country",
            "meta_description",
            "meta_title",
            "resolved_metadata",
            "url",
            "tags",
            "category_attributes",
            "photos",
        )
        read_only_fields = ("slug", "publisher", "publish_date", "update_date", "hits", "url", "tags", "photos")
        extra_kwargs = {
            "title": {"required": True},
            "text": {"required": True},
        }

    def validate(self, attrs):
        category = attrs.get("rubric") or getattr(self.instance, "rubric", None)
        if category and "category_attributes" in attrs:
            try:
                supplied = validate_category_attributes(category, attrs["category_attributes"])
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"category_attributes": exc.messages}) from exc
            historical = dict(getattr(self.instance, "category_attributes", {}) or {})
            historical.pop(str(category.pk), None)
            historical.update(supplied)
            attrs["category_attributes"] = historical
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        category = Category.objects.select_for_update().get(pk=validated_data["rubric"].pk)
        if "category_attributes" in validated_data:
            try:
                validated_data["category_attributes"] = validate_category_attributes(
                    category, validated_data["category_attributes"]
                )
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"category_attributes": exc.messages}) from exc
        post = super().create(validated_data)
        rebuild_post_attribute_values(post)
        return post

    @transaction.atomic
    def update(self, instance, validated_data):
        # Serialize editorial writes before replacing the JSON and derived rows.
        instance = Post.objects.select_for_update().get(pk=instance.pk)
        if "category_attributes" in validated_data or "rubric" in validated_data:
            category = validated_data.get("rubric", instance.rubric)
            Category.objects.select_for_update().get(pk=category.pk)
        if "category_attributes" in validated_data:
            category = validated_data.get("rubric", instance.rubric)
            supplied = validated_data["category_attributes"].get(str(category.pk), {})
            try:
                validated = validate_category_attributes(category, {str(category.pk): supplied})
                supplied = validated.get(str(category.pk), {})
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"category_attributes": exc.messages}) from exc
            historical = dict(instance.category_attributes or {})
            historical.pop(str(category.pk), None)
            if supplied:
                historical[str(category.pk)] = supplied
            validated_data["category_attributes"] = historical
        changed = "category_attributes" in validated_data or "rubric" in validated_data
        post = super().update(instance, validated_data)
        if changed:
            rebuild_post_attribute_values(post)
        return post

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rubric"] = PostCategorySerializer(instance.rubric).data
        data["country"] = PostCountrySerializer(instance.country).data if instance.country else None
        return data

    def get_resolved_metadata(self, instance):
        return resolve_publication_metadata(instance)
