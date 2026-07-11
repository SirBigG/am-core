from django.db.models import Q
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from api.v1.content.serializers import CategoryTreeSerializer, ContentPostSerializer, CountrySerializer
from core.classifier.models import Category, Country
from core.posts.models import Post


class ContentTokenMixin:
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)


class ContentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class CategoryTreeView(ContentTokenMixin, ListAPIView):
    serializer_class = CategoryTreeSerializer
    pagination_class = None

    def get_queryset(self):
        return Category.objects.filter(parent=None, is_active=True).order_by("tree_id", "lft")


class CountryListView(ContentTokenMixin, ListAPIView):
    serializer_class = CountrySerializer
    pagination_class = None
    queryset = Country.objects.all().order_by("value", "id")


class PostListCreateView(ContentTokenMixin, ListCreateAPIView):
    serializer_class = ContentPostSerializer
    pagination_class = ContentPagination

    def get_queryset(self):
        queryset = Post.objects.select_objects().prefetch_related("tags").order_by("-id")
        rubric = self.request.query_params.get("rubric")
        country = self.request.query_params.get("country")
        if rubric:
            rubric_query = Q(rubric__slug=rubric)
            if rubric.isdigit():
                rubric_query |= Q(rubric_id=int(rubric))
            queryset = queryset.filter(rubric_query)
        if country:
            country_query = Q(country__slug=country) | Q(country__short_slug=country)
            if country.isdigit():
                country_query |= Q(country_id=int(country))
            queryset = queryset.filter(country_query)
        return queryset

    def perform_create(self, serializer):
        serializer.save(publisher=self.request.user)


class PostUpdateView(ContentTokenMixin, RetrieveUpdateAPIView):
    serializer_class = ContentPostSerializer
    http_method_names = ("get", "put", "patch", "head", "options")

    def get_queryset(self):
        return Post.objects.select_objects().prefetch_related("tags").filter(publisher=self.request.user)

    def perform_update(self, serializer):
        serializer.save(publisher=self.request.user, update_date=timezone.now())
