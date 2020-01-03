from core.pro_auth.models import User

from api.v1.pro_auth.serializers import UserSerializer
from api.v1.pro_auth.permissions import PersonalPermission

from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated


class UserViewSet(ModelViewSet):
    serializer_class = UserSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated, PersonalPermission]

    def get_object(self):
        return self.request.user
