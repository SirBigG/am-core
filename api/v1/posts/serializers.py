from __future__ import unicode_literals

from rest_framework import serializers

from core.posts.models import Post, Photo
from core.classifier.models import Category


class AbsoluteUrlMixin(object):
    def get_abs_url(self, instance):
        return instance.get_absolute_url()


class PhotoSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=False)
    author = serializers.CharField(required=False)
    source = serializers.CharField(required=False)
    image = serializers.ImageField()

    class Meta:
        model = Photo
        fields = ('description', 'author', 'source', 'image')


class PhotoThumbnailSerializer(PhotoSerializer):
    """For make thumbnails in lists."""
    # TODO: parametrization
    image = serializers.SerializerMethodField()

    @staticmethod
    def get_image(obj):
        return obj.thumbnail(340, 230)


class PostSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=500)
    text = serializers.CharField()
    author = serializers.CharField(max_length=250)
    source = serializers.CharField(max_length=250)
    status = serializers.BooleanField()
    photo = PhotoSerializer(many=True, source='photo.all')

    class Meta:
        model = Post
        fields = ('title', 'text', 'author', 'source',
                  'status', 'photo',)


class ShortPostSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    title = serializers.CharField(max_length=500)
    text = serializers.CharField()
    url = serializers.SerializerMethodField('get_abs_url')
    photo = PhotoSerializer(source='photo.first')

    class Meta:
        model = Post
        fields = ('title', 'text', 'url', 'photo',)


class ShortPostListSerializer(ShortPostSerializer):
    photo = PhotoThumbnailSerializer(source='photo.first')


class CategoryPKRelatedField(serializers.RelatedField):
    # TODO: changing null error message to required
    def to_internal_value(self, data):
        return self.get_queryset().get(pk=data)

    def to_representation(self, value):
        return {'pk': value.pk, 'value': str(value)}


class UserPostSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    """Serializer for user post view set.
       By default created with inactive status."""
    title = serializers.CharField(max_length=500)
    text = serializers.CharField()
    source = serializers.CharField(max_length=250, required=False)
    status = serializers.BooleanField(default=0)
    url = serializers.SerializerMethodField('get_abs_url')
    rubric = CategoryPKRelatedField(queryset=Category.objects.filter(level=1))
    photo = PhotoSerializer(source='photo.first', read_only=True)
    photos = serializers.ListField(child=serializers.ImageField(), required=False, allow_empty=False)

    class Meta:
        model = Post
        fields = ('title', 'text', 'source',
                  'status', 'rubric', 'url', 'photos', 'photo',)

    def create(self, validated_data):
        """For related objects created."""
        photos = validated_data.pop('photos')
        rubric = validated_data.pop('rubric')
        user_rubric, created = Category.objects.get_or_create(defaults={"slug": "%s-user" % rubric.slug},
                                                              **{"parent": rubric,
                                                                 "value": "Статті користувачів"})
        validated_data.update({'rubric': user_rubric})
        post = Post.objects.create(**validated_data)
        for image in photos:
            Photo.objects.create(image=image, post=post)
        return post
