from rest_framework import serializers

from appl.posts.models import Post, Photo
from appl.classifier.models import Category


class AbsoluteUrlMixin(object):
    def get_abs_url(self, instance):
        return instance.get_absolute_url()


class PhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField('get_image_url')
    description = serializers.CharField(required=False)
    author = serializers.CharField(required=False)
    source = serializers.CharField(required=False)

    def get_image_url(self, instance):
        return instance.image.url

    class Meta:
        model = Photo
        fields = ('url', 'description', 'author', 'source',)


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


class CategoryPKRelatedField(serializers.RelatedField):
    def to_internal_value(self, data):
        return self.get_queryset().get(pk=data)

    def to_representation(self, value):
        return {'pk': value.pk, 'value': str(value)}


# TODO: automatic slug field if object created
class UserPostSerializer(AbsoluteUrlMixin, serializers.ModelSerializer):
    """Serializer for user post view set.
       By default created with inactive status."""
    title = serializers.CharField(max_length=500)
    text = serializers.CharField()
    author = serializers.CharField(max_length=250, required=False)
    source = serializers.CharField(max_length=250, required=False)
    status = serializers.BooleanField(default=0)
    photo = PhotoSerializer(source='photo.first')
    url = serializers.SerializerMethodField('get_abs_url')
    rubric = CategoryPKRelatedField(queryset=Category.objects.all())

    class Meta:
        model = Post
        fields = ('title', 'text', 'author', 'source',
                  'status', 'photo', 'rubric', 'url', 'publisher')
