"""Bounded image uploads for categories and visible article photos."""

from io import BytesIO
from uuid import uuid4

from django.contrib import admin
from django.contrib.admin.models import ADDITION, CHANGE, DELETION
from django.core.files.base import ContentFile
from django.db import models
from django.utils import timezone
from PIL import Image
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveUpdateAPIView, get_object_or_404
from rest_framework.viewsets import ModelViewSet

from core.classifier.models import Category, CategoryHub
from core.posts.models import Photo, Post

from .hubs import visible_posts
from .management import CropSetupAccess, audit
from .taxonomy import StrictFieldsMixin, lock_taxonomy
from .views import ContentPagination


class CropImageField(serializers.ImageField):
    def to_internal_value(self, data):
        if getattr(data, "size", 0) > 10 * 1024 * 1024:
            raise serializers.ValidationError("Images must be at most 10 MiB.")
        image = super().to_internal_value(data)
        if image.image.format not in ("JPEG", "PNG", "WEBP"):
            raise serializers.ValidationError("Upload a JPEG, PNG or WebP image.")
        width, height = image.image.size
        if width * height > 24000000 or max(width, height) > 12000:
            raise serializers.ValidationError("Images must fit within 24 megapixels and 12000 pixels per side.")
        return image


def store_image(instance, field_name, upload, context, thumbnail=None):
    field = instance._meta.get_field(field_name)
    with Image.open(upload) as image:
        image.seek(0)
        image = image.convert("RGBA" if "A" in image.getbands() or "transparency" in image.info else "RGB")
        if thumbnail:
            if field_name == "image" and isinstance(instance, Category):
                from PIL import ImageOps

                image = ImageOps.fit(image, thumbnail, method=Image.Resampling.LANCZOS)
            else:
                image.thumbnail(thumbnail, Image.Resampling.LANCZOS)
        output = BytesIO()
        image.save(output, format="WEBP", quality=85)
    name = field.generate_filename(instance, f"{uuid4().hex}.webp")
    name = field.storage.save(name, ContentFile(output.getvalue()))
    context["view"].uploaded_files.append((field.storage, name))
    return name


class CategoryImagesSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    image = CropImageField(required=False, allow_null=True)
    hero_image = CropImageField(required=False, allow_null=True)

    class Meta:
        model = Category
        fields = ("id", "image", "hero_image")

    def update(self, instance, validated_data):
        updates = {}
        for name, upload in validated_data.items():
            updates[name] = (
                store_image(
                    instance,
                    name,
                    upload,
                    self.context,
                    (300, 200) if name == "image" else None,
                )
                if upload is not None
                else ""
            )
        if updates:
            Category.objects.filter(pk=instance.pk).update(**updates)
        instance.refresh_from_db()
        CategoryHub.objects.update(updated=timezone.now())
        audit(self.context["request"], instance, CHANGE, validated_data)
        return instance


class CategoryImagesView(CropSetupAccess, RetrieveUpdateAPIView):
    serializer_class = CategoryImagesSerializer
    queryset = Category.objects.all()
    http_method_names = ("get", "patch", "head", "options")

    def update(self, request, *args, **kwargs):
        def perform():
            lock_taxonomy()
            self.queryset = self.queryset.select_for_update()
            return super(CategoryImagesView, self).update(request, *args, **kwargs)

        return self.mutate(perform)


class ContentPhotoSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    image = CropImageField()

    class Meta:
        model = Photo
        fields = ("id", "post", "image", "description", "author", "source")

    def get_fields(self):
        fields = super().get_fields()
        fields["post"].queryset = visible_posts(self.context["request"])
        return fields

    def validate(self, attrs):
        if self.instance and "post" in attrs and attrs["post"].pk != self.instance.post_id:
            raise serializers.ValidationError({"post": "Photo ownership cannot change."})
        post = attrs.get("post") or self.instance.post
        if not admin.site.get_model_admin(Post).has_change_permission(self.context["request"], post):
            raise PermissionDenied("Article change permission is required to maintain its photos.")
        return attrs

    def create(self, validated_data):
        instance = Photo(**{key: value for key, value in validated_data.items() if key != "image"})
        instance.image = store_image(instance, "image", validated_data["image"], self.context, (1000, 800))
        # The bounded upload pipeline already normalizes the file, replacing Photo.save's image rewrite.
        models.Model.save(instance, force_insert=True)
        return instance

    def update(self, instance, validated_data):
        if "image" in validated_data:
            validated_data["image"] = store_image(instance, "image", validated_data["image"], self.context, (1000, 800))
        if validated_data:
            Photo.objects.filter(pk=instance.pk).update(**validated_data)
        instance.refresh_from_db()
        return instance


class ContentPhotoViewSet(CropSetupAccess, ModelViewSet):
    serializer_class = ContentPhotoSerializer
    queryset = Photo.objects.select_related("post").order_by("pk")
    pagination_class = ContentPagination
    http_method_names = ("get", "post", "patch", "delete", "head", "options")

    def get_queryset(self):
        queryset = super().get_queryset().filter(post__in=visible_posts(self.request))
        post = self.request.query_params.get("post")
        if post is not None:
            if not post.isascii() or not post.isdecimal() or int(post) < 1:
                raise serializers.ValidationError({"post": "Use a positive integer ID."})
            queryset = queryset.filter(post_id=int(post))
        return queryset

    def create(self, request, *args, **kwargs):
        return self.mutate(lambda: super(ContentPhotoViewSet, self).create(request, *args, **kwargs))

    def update(self, request, *args, **kwargs):
        def perform():
            self.queryset = self.queryset.select_for_update(of=("self",))
            return super(ContentPhotoViewSet, self).update(request, *args, **kwargs)

        return self.mutate(perform)

    def perform_create(self, serializer):
        post = get_object_or_404(Post.objects.select_for_update(), pk=serializer.validated_data["post"].pk)
        if not admin.site.get_model_admin(Post).has_change_permission(self.request, post):
            raise PermissionDenied("Article change permission is required.")
        instance = serializer.save()
        audit(self.request, instance, ADDITION)

    def perform_update(self, serializer):
        instance = serializer.save()
        audit(self.request, instance, CHANGE, serializer.validated_data)

    def destroy(self, request, *args, **kwargs):
        def perform():
            self.queryset = self.queryset.select_for_update(of=("self",))
            return super(ContentPhotoViewSet, self).destroy(request, *args, **kwargs)

        return self.mutate(perform)

    def perform_destroy(self, instance):
        if not admin.site.get_model_admin(Post).has_change_permission(self.request, instance.post):
            raise PermissionDenied("Article change permission is required.")
        audit(self.request, instance, DELETION)
        instance.delete()
