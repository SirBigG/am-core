"""Explicit operator decisions about an offer's catalog identity."""

from django.contrib.admin.models import CHANGE
from django.utils import timezone
from rest_framework import serializers
from rest_framework.generics import RetrieveUpdateAPIView

from core.companies.models import Product
from core.posts.models import Post

from .hubs import visible_posts
from .management import CropSetupAccess, audit
from .taxonomy import StrictFieldsMixin


class ProductMatchSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    post_id = serializers.PrimaryKeyRelatedField(source="post", queryset=Post.objects.none(), allow_null=True)

    class Meta:
        model = Product
        fields = ("id", "name", "category_id", "post_id", "match_status", "match_reason")
        read_only_fields = ("name", "category_id", "match_status", "match_reason")

    def get_fields(self):
        fields = super().get_fields()
        fields["post_id"].queryset = visible_posts(self.context["request"]).select_for_update()
        return fields

    def validate(self, attrs):
        if "post" not in attrs:
            raise serializers.ValidationError({"post_id": "Supply an article ID or null to confirm no match."})
        post = attrs["post"]
        if post and (
            post.rubric_id != self.instance.category_id
            or not post.status
            or post.publish_date > timezone.now()
            or post.rubric.get_ancestors(include_self=True).filter(is_active=False).exists()
        ):
            raise serializers.ValidationError({"post_id": "Choose a public article in the product's exact category."})
        return attrs

    def update(self, instance, validated_data):
        instance.post = validated_data["post"]
        instance.match_status = Product.MatchStatus.CONFIRMED
        instance.match_reason = "Ручне рішення щодо прив’язки через API."
        instance.save(update_fields=["post", "match_status", "match_reason"])
        audit(self.context["request"], instance, CHANGE, ("post", "match_status", "match_reason"))
        return instance


class ProductMatchView(CropSetupAccess, RetrieveUpdateAPIView):
    queryset = Product.objects.all()
    serializer_class = ProductMatchSerializer
    http_method_names = ("get", "patch", "head", "options")

    def update(self, request, *args, **kwargs):
        def perform():
            self.queryset = self.queryset.select_for_update()
            return super(ProductMatchView, self).update(request, *args, **kwargs)

        return self.mutate(perform)
