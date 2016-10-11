from __future__ import unicode_literals

from core.services.models import Comments
from core.pro_auth.models import User

from rest_framework import serializers


class CommentsSerializer(serializers.ModelSerializer):

    user_sign = serializers.SerializerMethodField()
    creation = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S", read_only=True)

    class Meta:
        model = Comments
        fields = ('pk', 'object_id', 'user_sign', 'text', 'parent', 'creation', 'level',)

    @staticmethod
    def get_user_sign(instance):
        return str(instance.user)

    def create(self, validated_data):
        if not validated_data.get('parent'):
            _user = User.objects.get(email='admin@agromega.in.ua')
            root, status = Comments.objects.get_or_create(**{'object_id': validated_data.get('object_id'),
                                                             'content_type': validated_data.get('content_type'),
                                                             'user': _user,
                                                             'text': 'root'})
            validated_data.update({'parent': root})
        return Comments.objects.create(**validated_data)
