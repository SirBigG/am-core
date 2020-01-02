import logging

from django.utils.translation import get_language

from core.posts.models import Post, PostView as PostViewModel, UsefulStatistic

from api.v1.posts.serializers import UserPostSerializer, ShortPostListSerializer
from api.v1.posts.permissions import UserPostPermissions

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from transliterate import slugify


class SmallPagesPagination(PageNumberPagination):
    page_size = 10


class ApiPostList(ListAPIView):
    """Returns all active posts."""
    queryset = Post.objects.filter(status=1).order_by('-id')
    serializer_class = ShortPostListSerializer
    pagination_class = SmallPagesPagination


class RandomListPaginator(PageNumberPagination):
    page_size = 4


class RandomApiPostList(ListAPIView):
    """Returned five random post objects."""
    queryset = Post.objects.filter(status=1).order_by('?')
    serializer_class = ShortPostListSerializer
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


class PostView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        if request.data and 'fingerprint' in request.data:
            # todo: ref this with serializers usage or check keys not secure with kwargs.
            try:
                data = request.data.dict()
            except Exception as e:
                logging.error(e)
                data = request.data
            if PostViewModel.objects.filter(**data).exists() is False:
                PostViewModel.objects.create(**data)
                post = Post.objects.get(pk=request.data.get('post_id'))
                post.hits += 1
                post.save()
        return Response({"code": 200, "message": "Success"})


class PostUsefulView(APIView):
    permission_classes = []

    def post(self, request, *args, **kwargs):
        if request.data and 'fingerprint' in request.data:
            if UsefulStatistic.objects.filter(**request.data).exists() is False:
                UsefulStatistic.objects.create(**request.data)
        return Response({"code": 200, "message": "Success"})
