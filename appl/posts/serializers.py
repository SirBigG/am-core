from rest_framework import serializers

from appl.posts.models import Post, Photo


class PhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField('get_image_url')
    description = serializers.CharField()
    author = serializers.CharField()
    source = serializers.CharField()

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


class ShortPostSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=500)
    text = serializers.CharField()
    url = serializers.SerializerMethodField('get_abs_url')
    photo = PhotoSerializer(source='photo.first')

    class Meta:
        model = Post
        fields = ('title', 'text', 'url', 'photo',)

    def get_abs_url(self, instance):
        return instance.get_absolute_url()
