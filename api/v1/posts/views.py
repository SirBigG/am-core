from __future__ import unicode_literals

from django.utils.translation import get_language

from core.posts.models import Post

from api.v1.posts.serializers import ShortPostSerializer, UserPostSerializer
from api.v1.posts.permissions import UserPostPermissions

from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from transliterate import slugify


class SmallPagesPagination(PageNumberPagination):
    page_size = 10


class ApiPostList(ListAPIView):
    """Returns all active posts."""
    queryset = Post.objects.filter(status=1).order_by('-id')
    serializer_class = ShortPostSerializer
    pagination_class = SmallPagesPagination


class RandomListPaginator(PageNumberPagination):
    page_size = 4


class RandomApiPostList(ListAPIView):
    """Returned five random post objects."""
    queryset = Post.objects.filter(status=1).order_by('?')
    serializer_class = ShortPostSerializer
    pagination_class = RandomListPaginator


class UserPostsViewSet(ModelViewSet):
    """Working just with user posts."""
    serializer_class = UserPostSerializer
    pagination_class = SmallPagesPagination
    permission_classes = [UserPostPermissions, IsAuthenticated]

    def get_queryset(self):
        return Post.objects.filter(publisher=self.request.user)

    def perform_create(self, serializer):
        """Adding some extra data to created object."""
        _lang = get_language()[:2]
        slug = slugify(self.request.data.get('title'), _lang)
        serializer.save(publisher=self.request.user, slug=slug)
