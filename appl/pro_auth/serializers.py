from rest_framework import serializers

from appl.pro_auth.models import User
from appl.classifier.models import Location

from phonenumber_field.validators import validate_international_phonenumber

from django.utils.translation import ugettext as _


class LocationPKRelatedField(serializers.RelatedField):
    def to_internal_value(self, data):
        return self.get_queryset().select_related('country', 'region', 'area').get(pk=data)

    def to_representation(self, value):
        return {'pk': value.pk, 'value': str(value)}


class UserSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    phone1 = serializers.CharField(validators=[validate_international_phonenumber], label=_("Phone"))
    phone2 = serializers.CharField(validators=[validate_international_phonenumber], label=_("Phone"),
                                   required=False)
    phone3 = serializers.CharField(validators=[validate_international_phonenumber], label=_("Phone"),
                                   required=False)
    location = LocationPKRelatedField(queryset=Location.objects.all())
    birth_date = serializers.DateField(required=False)
    avatar = serializers.ImageField(required=False)
    avatar_url = serializers.SerializerMethodField('get_image_url')

    class Meta:
        model = User
        fields = ('pk', 'email', 'first_name', 'last_name', 'phone1', 'phone2', 'phone3',
                  'birth_date', 'location', 'avatar', 'avatar_url')

    @staticmethod
    def get_image_url(instance):
        """Image location return if file upload else return something."""
        try:
            url = instance.avatar.url
        except ValueError:
            url = ''
        return url
