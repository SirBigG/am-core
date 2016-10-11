from __future__ import unicode_literals

from core.pro_auth.models import User

from api.v1.pro_auth.serializers import UserSerializer
from api.v1.pro_auth.permissions import PersonalPermission

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated


# TODO: authentication required need
# TODO: get method for update form creation
# TODO: create tokenize authenticate or other for all api login required connections
class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, PersonalPermission]
