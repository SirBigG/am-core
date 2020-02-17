from api.v1.classifiers.serializers import LocationSerializer, CategorySerializer, FullCategorySerializer

from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from core.classifier.models import Location, Category


class LocationPagination(PageNumberPagination):
    page_size = 10


class LocationListView(ListAPIView):
    serializer_class = LocationSerializer
    pagination_class = LocationPagination

    def get_queryset(self):
        qs = Location.objects.all()
        loc = self.request.query_params.get('loc', None)
        if loc:
            qs = qs.filter(value__istartswith=loc)
        return qs


class CategoryListView(ListAPIView):
    """Returns categories list. Not paginated response.
       Filters: level - level in tree"""
    serializer_class = CategorySerializer

    def get_queryset(self):
        q = Category.objects.all()
        level = self.request.query_params.get('level', None)
        if level:
            q = q.filter(level=level)
        return q


class CategoriesTreeView(APIView):
    def get(self, request, *args, **kwargs):
        to_response = []
        for root in Category.objects.filter(level=0, is_active=True).order_by("value"):
            node = FullCategorySerializer(root).data
            node["children"] = FullCategorySerializer(root.get_children(), many=True).data
            to_response.append(node)
            print(node)
        return Response(data=to_response)
