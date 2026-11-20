from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.exceptions import NotFound
from rest_framework.parsers import JSONParser
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from api.v1.content.views import ContentTokenMixin
from core.posts.models import Post
from core.registry.models import Company, Variety


class AddCompanyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Company.save_company_from_row(row)
        return Response({"status": "ok"})


class AddActiveVarietyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Variety.save_active_variety_from_row(row)
        return Response({"status": "ok"})


class AddInactiveVarietyView(APIView):
    permission_classes = [
        IsAdminUser,
    ]

    def post(self, request, *args, **kwargs):
        row = request.data.get("row")
        Variety.save_inactive_variety_from_row(row)
        return Response({"status": "ok"})


class VarietyPublicationSerializer(serializers.Serializer):
    publication_id = serializers.JSONField()

    def validate_publication_id(self, value):
        if type(value) is not int or value < 1:
            raise serializers.ValidationError("A positive integer is required.")
        return value


class VarietyPublicationView(ContentTokenMixin, APIView):
    parser_classes = (JSONParser,)
    permission_classes = (IsAdminUser,)

    def patch(self, request, variety_id):
        serializer = VarietyPublicationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        publication_id = serializer.validated_data["publication_id"]

        with transaction.atomic():
            variety = get_object_or_404(Variety.objects.select_for_update(), pk=variety_id)
            publications = Post.objects.all()
            if variety.publication_id is None:
                # Keep the target from being deleted before the foreign key is saved.
                publications = publications.select_for_update(no_key=True)
            if not publications.filter(pk=publication_id).exists():
                raise NotFound("Publication not found.")

            if variety.publication_id is None:
                variety.publication_id = publication_id
                variety.save(update_fields=("publication",))

            result = {"variety_id": variety.pk, "publication_id": variety.publication_id}
            if variety.publication_id != publication_id:
                return Response(
                    {
                        **result,
                        "code": "publication_conflict",
                        "detail": "Variety already has a different publication.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

        return Response(result)
