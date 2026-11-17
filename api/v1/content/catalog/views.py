"""Private editorial API for the shared catalog relation service."""

import hashlib
import json
import re
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.cache import add_never_cache_headers
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.pagination import CursorPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from core.catalog.models import CatalogEntityKind
from core.catalog.relation_access import RelationAccess, configured_relation_site
from core.catalog.relation_service import RelationConflict
from core.catalog.relations import ImportReceipt, RelationAuditEvent, RelationTypeVersion

from ..views import ContentTokenMixin
from .serializers import (
    DraftSerializer,
    EmptySerializer,
    ReinstatementSerializer,
    ReleaseSerializer,
    ReviewSerializer,
    WithdrawalSerializer,
    validate_database_text,
)


class CatalogError(APIException):
    def __init__(self, status, code, detail):
        self.status_code = status
        super().__init__(detail=detail, code=code)
        self.catalog_code = code


def etag(record):
    return f'"{record.pk}:{record.lock_version}"'


def revision_data(revision):
    participants = {}
    for item in revision.participants.order_by("role", "ordinal"):
        participants.setdefault(item.role, []).append(str(item.entity_id))
    return {
        "id": str(revision.pk),
        "record_id": str(revision.record_id),
        "number": revision.number,
        "type_code": revision.schema.relation_type_id,
        "schema_version": revision.schema.version,
        "state": revision.state,
        "participants": participants,
        "payload": revision.payload,
        "source": revision.source,
        "country": revision.country,
        "source_version_digest": revision.source_version_digest,
        "base_approved_revision_id": (
            str(revision.base_approved_revision_id) if revision.base_approved_revision_id else None
        ),
        "created_by": revision.created_by_id,
        "created_at": revision.created_at.isoformat(),
        "reviewed_by": revision.reviewed_by_id,
        "reviewed_at": revision.reviewed_at.isoformat() if revision.reviewed_at else None,
    }


def record_data(record, site_id):
    latest = record.revisions.select_related("schema").order_by("-number").first()
    release = record.releases.filter(site_id=site_id).first()
    withdrawal = record.withdrawals.order_by("-resulting_epoch").first()
    return {
        "id": str(record.pk),
        "type_code": record.relation_type_id,
        "lock_version": record.lock_version,
        "etag": etag(record),
        "archived": record.archived,
        "withdrawn": record.withdrawn,
        "withdrawal": (
            {
                "id": str(withdrawal.pk),
                "epoch": withdrawal.resulting_epoch,
                "reason": withdrawal.reason,
                "evidence": withdrawal.evidence,
            }
            if withdrawal
            else None
        ),
        "latest_revision": revision_data(latest) if latest else None,
        "release": (
            {
                "enabled": release.enabled,
                "approved_revision_id": str(release.approved_revision_id),
            }
            if release
            else None
        ),
    }


class CatalogPagination(CursorPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
    ordering = "id"


class PrivateCatalogView(ContentTokenMixin, APIView):
    permission_classes = (IsAdminUser,)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        add_never_cache_headers(response)
        response["X-Robots-Tag"] = "noindex, nofollow"
        return response

    def handle_exception(self, exc):
        if isinstance(exc, DjangoValidationError):
            code = getattr(exc, "code", "validation_error") or "validation_error"
            if code == "invalid":
                code = "validation_error"
            status = 409 if isinstance(exc, RelationConflict) or code == "duplicate_relation" else 400
            exc = CatalogError(status, code, exc.messages)
        elif isinstance(exc, IntegrityError):
            exc = CatalogError(409, "conflicting_write", "Conflicting write. Read current state before retrying.")
        response = super().handle_exception(exc)
        code = getattr(exc, "catalog_code", None)
        if code is None:
            code = {
                400: "validation_error",
                401: "authentication_required",
                403: "permission_denied",
                404: "not_found",
                405: "method_not_allowed",
            }.get(response.status_code, "request_failed")
        response.data = {"version": 1, "error": {"code": code, "detail": response.data}}
        return response


class CatalogView(PrivateCatalogView):
    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.access = RelationAccess(request.user, configured_relation_site())
        self.access._grant()

    def query(self, allowed=()):
        validate_database_text(self.request.query_params)
        permitted = set(allowed) | {"cursor", "page_size"}
        if set(self.request.query_params) - permitted:
            raise ValidationError("Unknown query parameters are not allowed.")
        if any(len(self.request.query_params.getlist(key)) != 1 for key in self.request.query_params):
            raise ValidationError("Query parameters must be supplied once.")
        size = self.request.query_params.get("page_size")
        if size is not None and (
            len(size) > 2 or not size.isascii() or not size.isdecimal() or not 1 <= int(size) <= 50
        ):
            raise ValidationError("page_size must be between 1 and 50.")
        return self.request.query_params

    def page(self, queryset, represent, ordering="id"):
        pagination = CatalogPagination()
        pagination.ordering = ordering
        rows = pagination.paginate_queryset(queryset, self.request, view=self)
        response = pagination.get_paginated_response([represent(item) for item in rows])
        response.data["version"] = 1
        return response

    def record(self, record_id):
        return get_object_or_404(self.access.records(), pk=record_id)

    def expected_version(self, record, *, replay=False):
        header = self.request.headers.get("If-Match")
        if header is None:
            raise CatalogError(428, "missing_precondition", "Supply the record ETag in If-Match.")
        if replay:
            match = re.fullmatch(r'"' + str(record.pk) + r':([1-9][0-9]{0,18})"', header)
            if match:
                return int(match.group(1))
        if header != etag(record):
            raise CatalogError(409, "stale_version", "Record version changed. Read current state.")
        return record.lock_version

    def body(self, serializer_class):
        serializer = serializer_class(data=self.request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def record_response(self, record, *, status=200):
        record.refresh_from_db()
        return Response(
            {"version": 1, "record": record_data(record, self.access.site_id)},
            status=status,
            headers={"ETag": etag(record)},
        )

    def operation_scope(self):
        return f"editorial-api:v1:{self.access.site_id}:{self.request.user.pk}"

    @transaction.atomic
    def save_draft(self, record=None):
        data = self.body(DraftSerializer)
        permission = "change_relationrecord" if record else "add_relationrecord"
        grant = self.access._grant(permission=permission, write=True)
        if record and data["type_code"] != record.relation_type_id:
            raise CatalogError(409, "identity_change_requires_correction", "A revision must retain its relation type.")
        key = self.request.headers.get("Idempotency-Key", "")
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", key) is None:
            raise ValidationError(
                "Supply an Idempotency-Key of 1–128 ASCII letters, digits, dots, underscores or hyphens."
            )
        digest = hashlib.sha256(
            json.dumps(
                {"path": self.request.path, "body": data, "if_match": self.request.headers.get("If-Match")},
                cls=DjangoJSONEncoder,
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        receipt = ImportReceipt.objects.filter(actor_scope=self.operation_scope(), operation_key=key).first()
        if receipt:
            if receipt.request_digest != digest:
                raise CatalogError(409, "idempotency_conflict", "Operation key already used with different input.")
            self.access._require_record(grant, receipt.result["record_id"])
            return Response(
                receipt.result["body"],
                status=201,
                headers={"ETag": receipt.result["etag"], "Idempotent-Replay": "true"},
            )
        version = self.expected_version(record) if record else None
        revision = self.access.save_draft(
            **data,
            record_id=record.pk if record else None,
            expected_version=version,
        )
        record = revision.record
        record.refresh_from_db()
        body = {"version": 1, "record": record_data(record, self.access.site_id), "revision_id": str(revision.pk)}
        ImportReceipt.objects.create(
            actor_scope=self.operation_scope(),
            operation_key=key,
            request_digest=digest,
            result={"record_id": str(record.pk), "body": body, "etag": etag(record)},
        )
        return Response(body, status=201, headers={"ETag": etag(record)})


class EntityTypesView(CatalogView):
    def get(self, request):
        self.query()
        return Response(
            {"version": 1, "results": [{"code": code, "label": label} for code, label in CatalogEntityKind.choices]}
        )


class RelationTypesView(CatalogView):
    def get(self, request):
        self.query()
        return self.page(
            RelationTypeVersion.objects.all(),
            lambda row: {
                "id": row.pk,
                "type_code": row.relation_type_id,
                "schema_version": row.version,
                "roles": row.roles,
                "identity_roles": row.identity_roles,
                "identity_fields": row.identity_fields,
            },
        )


class EntitiesView(CatalogView):
    def get(self, request):
        params = self.query({"q", "kind", "category", "schema", "role"})
        query = self.access.participants().select_related("entity", "post", "category")
        if kind := params.get("kind"):
            if kind not in CatalogEntityKind.values:
                raise ValidationError("Unknown entity kind.")
            query = query.filter(entity__kind=kind)
        if category := params.get("category"):
            if not category.isascii() or not category.isdecimal() or len(category) > 9:
                raise ValidationError("Invalid category ID.")
            query = query.filter(Q(category_id=int(category)) | Q(post__rubric_id=int(category)))
        if params.get("schema") or params.get("role"):
            schema_id, role = params.get("schema", ""), params.get("role", "")
            if not schema_id.isascii() or not schema_id.isdecimal() or len(schema_id) > 9:
                raise ValidationError("Supply a schema ID and role together.")
            schema = RelationTypeVersion.objects.filter(pk=int(schema_id)).first()
            if not schema or role not in schema.roles:
                raise ValidationError("Unknown schema or role.")
            query = query.filter(entity__kind__in=schema.roles[role]["kinds"])
        if term := params.get("q", "").strip():
            if len(term) > 200:
                raise ValidationError("Search term is too long.")
            search = (
                Q(post__title__icontains=term)
                | Q(category__value__icontains=term)
                | Q(entity__kind__icontains=term)
                | Q(post__rubric__value__icontains=term)
            )
            try:
                search |= Q(entity_id=UUID(term))
            except ValueError:
                pass
            query = query.filter(search)
        return self.page(
            query,
            lambda row: {
                "id": str(row.entity_id),
                "kind": row.entity.kind,
                "label": (
                    row.post.title if row.post_id else row.category.value if row.category_id else str(row.entity_id)
                ),
                "post_id": row.post_id,
                "category_id": row.category_id,
            },
            ordering="entity_id",
        )


class RelationsView(CatalogView):
    def get(self, request):
        params = self.query({"entity", "role", "type_code"})
        query = self.access.records()
        if type_code := params.get("type_code"):
            if not RelationTypeVersion.objects.filter(relation_type_id=type_code).exists():
                raise ValidationError("Unknown relation type.")
            query = query.filter(relation_type_id=type_code)
        if params.get("role") and not params.get("entity"):
            raise ValidationError("A role filter requires an entity.")
        if entity := params.get("entity"):
            try:
                entity_id = UUID(entity)
            except ValueError as exc:
                raise ValidationError("Invalid entity UUID.") from exc
            if not self.access.participants().filter(entity_id=entity_id).exists():
                raise Http404("Entity is unavailable.")
            participants = {"revisions__participants__entity_id": entity_id}
            if role := params.get("role"):
                definitions = RelationTypeVersion.objects.all()
                if type_code:
                    definitions = definitions.filter(relation_type_id=type_code)
                if not any(role in row.roles for row in definitions):
                    raise ValidationError("Unknown relation role.")
                participants["revisions__participants__role"] = role
            query = query.filter(**participants).distinct()
        return self.page(query, lambda row: record_data(row, self.access.site_id))

    def post(self, request):
        return self.save_draft()


class RelationDetailView(CatalogView):
    def get(self, request, record_id):
        self.query()
        return self.record_response(self.record(record_id))

    @transaction.atomic
    def delete(self, request, record_id):
        self.body(EmptySerializer)
        record = self.record(record_id)
        self.access.archive(record_id=record.pk, expected_version=self.expected_version(record))
        return self.record_response(record)


class RevisionsView(CatalogView):
    def get(self, request, record_id):
        self.query()
        record = self.record(record_id)
        return self.page(record.revisions.select_related("schema"), revision_data, ordering="-number")

    def post(self, request, record_id):
        return self.save_draft(self.record(record_id))


class RevisionActionView(CatalogView):
    @transaction.atomic
    def post(self, request, revision_id, action):
        # Resolve through authorized records before exposing a revision ID.
        from core.catalog.relations import RelationRevision

        revision = get_object_or_404(RelationRevision.objects.filter(record__in=self.access.records()), pk=revision_id)
        record = revision.record
        version = self.expected_version(record)
        if action == "submit":
            self.body(EmptySerializer)
            self.access.submit(record_id=record.pk, revision_id=revision.pk, expected_version=version)
        else:
            data = self.body(ReviewSerializer)
            self.access.review(
                record_id=record.pk,
                revision_id=revision.pk,
                expected_version=version,
                content_locale=data.get("content_locale", ""),
                approve=data["action"] == "approve",
            )
        return self.record_response(record)


class RecordActionView(CatalogView):
    @transaction.atomic
    def post(self, request, record_id, action):
        record = self.record(record_id)
        version = self.expected_version(record, replay=action == "withdraw")
        if action == "withdraw":
            data = self.body(WithdrawalSerializer)
            key = request.headers.get("Idempotency-Key", "")
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", key) is None:
                raise ValidationError("Withdrawal requires an Idempotency-Key.")
            withdrawal = self.access.withdraw_application(
                record_id=record.pk,
                expected_version=version,
                reason=data["reason"],
                evidence=data["evidence"],
                operation_key=key,
            )
            response = self.record_response(record)
            response.data["withdrawal_id"] = str(withdrawal.pk)
            return response
        elif action == "reinstate":
            data = self.body(ReinstatementSerializer)
            self.access.reinstate_application(record_id=record.pk, expected_version=version, **data)
        elif action == "archive":
            self.body(EmptySerializer)
            self.access.archive(record_id=record.pk, expected_version=version)
        else:
            data = self.body(ReleaseSerializer if action == "release" else EmptySerializer)
            if action == "release":
                revision_id = data["revision_id"]
            else:
                release = record.releases.filter(site_id=self.access.site_id).first()
                if release is None:
                    raise Http404("Site release is unavailable.")
                revision_id = release.approved_revision_id
            self.access.release(
                record_id=record.pk,
                revision_id=revision_id,
                expected_version=version,
                content_locale=data.get("content_locale", ""),
                enabled=action == "release",
            )
        return self.record_response(record)


class AuditView(CatalogView):
    def get(self, request, record_id):
        self.query()
        record = self.record(record_id)
        return self.page(
            RelationAuditEvent.objects.filter(record=record),
            lambda row: {
                "id": row.pk,
                "action": row.action,
                "actor": row.actor_id,
                "revision_id": str(row.revision_id) if row.revision_id else None,
                "base_version": row.base_version,
                "occurred_at": row.occurred_at.isoformat(),
                "result": row.result,
            },
        )


class OperationView(CatalogView):
    def get(self, request, operation_key):
        self.query()
        validate_database_text(operation_key)
        receipt = get_object_or_404(ImportReceipt, actor_scope=self.operation_scope(), operation_key=operation_key)
        self.record(receipt.result["record_id"])
        return Response(receipt.result["body"], headers={"ETag": receipt.result["etag"]})
