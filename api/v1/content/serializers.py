from rest_framework import serializers

from core.classifier.models import Category, Country
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

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["rubric"] = PostCategorySerializer(instance.rubric).data
        data["country"] = PostCountrySerializer(instance.country).data if instance.country else None
        return data
