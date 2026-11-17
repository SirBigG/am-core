import json

from django.contrib.admin.models import ADDITION, CHANGE
from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from core.catalog.access_models import RelationEntityGrant, RelationSiteGrant
from core.catalog.models import CatalogEntity, CatalogEntityKind, CatalogEntityState
from core.catalog.publication_eligibility import lock_publication_graph
from core.catalog.relation_access import configured_relation_site
from core.classifier.models import Category
from core.posts.models import Post

from ..management import audit
from .serializers import StrictSerializer
from .views import CatalogError, PrivateCatalogView


class EntityProvisioningSerializer(StrictSerializer):
    site_grant_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    anchor_type = serializers.ChoiceField(choices=("category", "post"))
    anchor_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    kind = serializers.ChoiceField(choices=CatalogEntityKind.values)
    entity_id = serializers.UUIDField(required=False)
    provenance = serializers.DictField(required=False, allow_empty=False)

    def validate(self, data):
        if data["anchor_type"] == "category" and data["kind"] != CatalogEntityKind.CROP:
            raise serializers.ValidationError({"kind": "A category requires a crop entity."})
        if ("entity_id" in data) == ("provenance" in data):
            raise serializers.ValidationError("Supply provenance to create an entity or entity_id to reuse one.")
        if "provenance" in data:
            provenance = data["provenance"]
            if len(json.dumps(provenance, ensure_ascii=False).encode("utf-8")) > 16_384:
                raise serializers.ValidationError({"provenance": "Provenance exceeds 16 KiB."})
            formulation = provenance.get("formulation_identity")
            if data["kind"] == CatalogEntityKind.PREPARATION and (
                not isinstance(formulation, str) or not formulation.strip() or len(formulation) > 200
            ):
                raise serializers.ValidationError({"provenance": "A preparation needs a formulation identity."})
        return data


class EntityProvisioningView(PrivateCatalogView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_superuser:
            raise PermissionDenied("Catalog entity provisioning is unavailable.")

    @transaction.atomic
    def post(self, request):
        serializer = EntityProvisioningSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lock_publication_graph()
        if (
            not get_user_model()
            .objects.select_for_update()
            .filter(pk=request.user.pk, is_active=True, is_staff=True, is_superuser=True)
            .exists()
        ):
            raise PermissionDenied("Catalog entity provisioning is unavailable.")
        site_grant = get_object_or_404(
            RelationSiteGrant.objects.select_for_update(of=("self",)),
            pk=data["site_grant_id"],
            site_id=configured_relation_site(),
            actor__is_active=True,
            actor__is_staff=True,
        )
        anchor_type = data["anchor_type"]
        model = Category if anchor_type == "category" else Post
        anchor = get_object_or_404(model.objects.select_for_update(), pk=data["anchor_id"])
        entity, created = self.resolve_entity(request, anchor, data)
        if anchor.entity_id is None:
            anchor.entity = entity
            model.objects.filter(pk=anchor.pk).update(entity=entity)
            audit(request, anchor, CHANGE, ("entity",))
        grant, grant_created = RelationEntityGrant.objects.get_or_create(
            grant=site_grant, entity=entity, defaults={anchor_type: anchor}
        )
        if grant_created:
            audit(request, grant, ADDITION)
        elif any(label and label.entity_id != entity.pk for label in (grant.post, grant.category)):
            raise CatalogError(409, "grant_anchor_conflict", "The existing grant has an incompatible label anchor.")
        return Response(
            {
                "version": 1,
                "site_id": site_grant.site_id,
                "site_grant_id": site_grant.pk,
                "entity_id": str(entity.pk),
                "entity_grant_id": grant.pk,
                "anchor_type": anchor_type,
                "anchor_id": anchor.pk,
                "kind": entity.kind,
            },
            status=201 if created or grant_created else 200,
        )

    @staticmethod
    def resolve_entity(request, anchor, data):
        requested_id = data.get("entity_id")
        if requested_id and anchor.entity_id not in (None, requested_id):
            raise CatalogError(409, "entity_conflict", "The anchor already has a different catalog entity.")
        entity_id = anchor.entity_id or requested_id
        if entity_id:
            entity = get_object_or_404(CatalogEntity.objects.select_for_update(), pk=entity_id)
            if (
                entity.state != CatalogEntityState.ACTIVE
                or entity.kind != data["kind"]
                or ("provenance" in data and entity.provenance != data["provenance"])
            ):
                raise CatalogError(409, "entity_conflict", "The catalog entity differs from the request.")
            return entity, False
        entity = CatalogEntity.objects.create(kind=data["kind"], provenance=data["provenance"], created_by=request.user)
        audit(request, entity, ADDITION)
        return entity, True
