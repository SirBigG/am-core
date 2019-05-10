from api.v1.classifiers.serializers import LocationSerializer, CategorySerializer

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
        loc = self.request.query_params.get('loc')
        if loc:
            qs = qs.filter(value__istartswith=loc)
        return qs


class CategoryListView(ListAPIView):
    """Returns categories list. Not paginated response.
       Filters: level - level in tree"""
    serializer_class = CategorySerializer

    def get_queryset(self):
        q = Category.objects.all()
        level = self.request.query_params.get('level')
        if level:
            q = q.filter(level=level)
        if self.request.query_params.get("slug"):
            q = q.filter(parent__slug=self.request.query_params.get("slug"))
        return q


def get_node(node):
    for i in Category.objects.filter(parent__slug=node['slug']):
        node['nodes'].append(get_node({"level": i.level, "key": i.slug, "slug": i.slug, "label": i.value, "nodes": []}))
    return node


class CategoryTree(APIView):
    def _get_children(self, parent):
        return Category.objects.get(parent=parent)

    def get(self, request, *args, **kwargs):
        tree = get_node({"slug": "root", "key": "root", "level": 0, "parent_slug": "root",
                         "label": "root", "nodes": []})
        return Response(tree.get("nodes"))
