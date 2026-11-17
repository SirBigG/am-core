"""Read-only previews and atomic catalog batches on the shared access
policy."""

import hashlib
import json
import re
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.http import Http404
from django.utils import timezone

from core.classifier.models import Category
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.posts.models import Post
from core.posts.publication_checks import SitePostPublication, material_digest

from . import relation_service
from .access_models import RelationEntityGrant, RelationSiteGrant
from .application_models import (
    ApplicationCountryPolicy,
    ApplicationMethod,
    ApplicationReviewerGrant,
    PlantProtectionApplicationDetails,
)
from .models import CatalogEntity
from .publication_eligibility import lock_publication_graph
from .relation_access import RelationAccess
from .relations import (
    EntityPresentationSelection,
    ImportReceipt,
    RelationRecord,
    RelationRevision,
    RelationType,
    RelationTypeVersion,
)
from .validation import validate_database_text

SALT = "catalog-batch-preview-v1"
MAX_ITEMS = 50
OPERATIONS = {
    "drafts": ("add_relationrecord", "can_edit"),
    "submit": ("change_relationrecord", "can_edit"),
    "approve": ("review_relationrecord", "can_review"),
    "reject": ("review_relationrecord", "can_review"),
    "publish": ("publish_relationrecord", "can_publish"),
    "unpublish": ("publish_relationrecord", "can_publish"),
    "archive": ("change_relationrecord", "can_edit"),
    "withdraw_source": ("withdraw_relation", "can_review"),
    "reconcile_source": ("withdraw_relation", "can_review"),
}
DRAFT_FIELDS = {"type_code", "schema_version", "participants", "payload", "source", "country", "source_version_digest"}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, cls=DjangoJSONEncoder, sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def record_etag(record):
    return f'"{record.pk}:{record.lock_version}"'


def normalize_batch(value):
    try:
        value = json.loads(json.dumps(value, cls=DjangoJSONEncoder, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise ValidationError("Batch input must contain JSON values.") from exc
    if not isinstance(value, dict) or set(value) != {"operation", "operation_key", "items"}:
        raise ValidationError("Batch requires operation, operation_key and items only.")
    validate_database_text(value)
    operation, key, items = value["operation"], value["operation_key"], value["items"]
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValidationError("Unknown catalog batch operation.")
    if not isinstance(key, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", key) is None:
        raise ValidationError("Use an operation_key of 1–128 ASCII letters, digits, dots, underscores or hyphens.")
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValidationError("A batch must contain between 1 and 50 items.")
    if operation in {"withdraw_source", "reconcile_source"}:
        from .bulk_source import normalize_source_batch

        return normalize_source_batch(operation, key, items)
    seen, records = set(), set()
    result = []
    for item in items:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("key"), str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", item["key"]) is None
        ):
            raise ValidationError("Each item requires a unique ASCII key of 1–128 characters.")
        if item["key"] in seen:
            raise ValidationError("Item keys must be unique within the batch.")
        seen.add(item["key"])
        allowed = {"key", "record_id", "if_match"}
        if operation == "drafts":
            allowed.add("draft")
            data = item.get("draft")
            if (
                not isinstance(data, dict)
                or set(data) - DRAFT_FIELDS
                or not {"type_code", "schema_version", "participants"}.issubset(data)
            ):
                raise ValidationError(
                    "Drafts require type_code, schema_version and participants with documented fields only."
                )
            if (
                not isinstance(data["type_code"], str)
                or len(data["type_code"]) > 64
                or not isinstance(data["schema_version"], int)
                or isinstance(data["schema_version"], bool)
                or not 1 <= data["schema_version"] <= 2147483647
            ):
                raise ValidationError("Invalid draft type or schema version.")
            if not isinstance(data["participants"], dict) or any(
                not isinstance(ids, list) or len(ids) > 50 for ids in data["participants"].values()
            ):
                raise ValidationError("Participants must be explicit bounded UUID lists grouped by role.")
        elif operation in {"submit", "approve", "reject", "publish"}:
            allowed.add("revision_id")
            if "revision_id" not in item:
                raise ValidationError("This operation requires a revision_id.")
        if operation in {"approve", "reject", "publish"}:
            allowed.add("content_locale")
        if set(item) - allowed:
            raise ValidationError("Unknown batch item fields are not allowed.")
        if operation != "drafts" and "record_id" not in item:
            raise ValidationError("This operation requires a record_id.")
        normalized = dict(item)
        for field in ("record_id", "revision_id"):
            if field in item:
                try:
                    normalized[field] = str(UUID(str(item[field])))
                except (ValueError, TypeError, AttributeError) as exc:
                    raise ValidationError("Invalid batch record or revision UUID.") from exc
        if "record_id" in item:
            if not isinstance(item.get("if_match"), str):
                raise ValidationError("Each existing record requires its current if_match ETag.")
            if normalized["record_id"] in records:
                raise ValidationError("Select an existing record once per batch.")
            records.add(normalized["record_id"])
        elif "if_match" in item:
            raise ValidationError("A create item cannot supply if_match.")
        locale = item.get("content_locale", "")
        if not isinstance(locale, str) or len(locale) > 16 or (operation in {"approve", "publish"} and not locale):
            raise ValidationError("Approval/publication requires an explicit content language.")
        result.append(normalized)
    return {"operation": operation, "operation_key": key, "items": sorted(result, key=lambda row: row["key"])}


def draft_content(revision):
    grouped = {}
    for participant in revision.participants.order_by("role", "entity_id"):
        grouped.setdefault(participant.role, []).append(str(participant.entity_id))
    return {
        "type_code": revision.schema.relation_type_id,
        "schema_version": revision.schema.version,
        "participants": grouped,
        "payload": revision.payload,
        "source": revision.source,
        "country": revision.country,
        "source_version_digest": revision.source_version_digest,
    }


def prepared_content(prepared):
    return {
        "type_code": prepared["schema"].relation_type_id,
        "schema_version": prepared["schema"].version,
        "participants": {role: [str(pk) for pk in ids] for role, ids in prepared["participants"].items() if ids},
        "payload": prepared["payload"],
        "source": prepared["source"],
        "country": prepared["country"],
        "source_version_digest": prepared["source_version_digest"],
    }


class CatalogBatch:
    def __init__(self, access):
        self.access = access

    @property
    def scope(self):
        return f"catalog-batch:v1:{self.access.site_id}:{self.access.actor.pk}"

    def refresh_authority(self):
        if not self.access.actor.is_authenticated:
            raise PermissionDenied("Catalog batch actor is unavailable.")
        try:
            self.access.actor.refresh_from_db(fields=["is_active", "is_staff", "is_superuser"])
        except self.access.actor.__class__.DoesNotExist as exc:
            raise PermissionDenied("Catalog batch actor is unavailable.") from exc
        for name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
            self.access.actor.__dict__.pop(name, None)

    def authorize_batch(self, batch):
        return self.authorize(batch["operation"], revise=all("record_id" in item for item in batch["items"]))

    def authorize(self, operation, *, revise=False):
        permission, capability = OPERATIONS[operation]
        if operation == "drafts" and revise:
            permission = "change_relationrecord"
        return self.access._grant(permission=permission, write=True, capability=capability)

    def record(self, record_id, grant):
        self.access._require_record(grant, record_id)
        return RelationRecord.objects.select_for_update().get(pk=record_id)

    def lifecycle(self, operation, item, *, validate_only):
        record_id = item["record_id"]
        record = self.access.records().get(pk=record_id)
        if item["if_match"] != record_etag(record):
            raise relation_service.RelationConflict("Record version changed.", code="stale_version")
        args = {"record_id": record.pk, "expected_version": record.lock_version, "validate_only": validate_only}
        if operation == "archive":
            return self.access.archive(**args)
        if operation == "unpublish":
            release = record.releases.filter(site_id=self.access.site_id).first()
            if release is None:
                raise Http404("Site release is unavailable.")
            return self.access.release(
                **args, revision_id=release.approved_revision_id, content_locale="", enabled=False
            )
        if operation == "submit":
            return self.access.submit(**args, revision_id=item["revision_id"])
        if operation in {"approve", "reject"}:
            return self.access.review(
                **args,
                revision_id=item["revision_id"],
                content_locale=item.get("content_locale", ""),
                approve=operation == "approve",
            )
        return self.access.release(
            **args, revision_id=item["revision_id"], content_locale=item["content_locale"], enabled=True
        )

    def plan_item(self, batch, item, identities):
        operation = batch["operation"]
        grant = self.authorize(operation, revise="record_id" in item)
        self.access._lock_participant_scope(grant)
        if operation == "drafts":
            self.access._require_participants(grant, item["draft"]["participants"])
            prepared = relation_service.prepare_draft(**item["draft"])
            identity = (prepared["schema"].relation_type_id, prepared["identity_digest"])
            if "record_id" in item:
                record = self.record(item["record_id"], grant)
                if item["if_match"] != record_etag(record):
                    raise relation_service.RelationConflict("Record version changed.", code="stale_version")
                if (
                    record.relation_type_id != identity[0]
                    or record.identity_digest != prepared["identity_digest"]
                    or record.identity != prepared["identity"]
                ):
                    raise relation_service.RelationConflict(
                        "Use explicit identity correction.", code="identity_change_requires_correction"
                    )
            else:
                record = RelationRecord.objects.filter(
                    relation_type_id=identity[0], identity_digest=identity[1]
                ).first()
                if record:
                    self.access._require_record(grant, record.pk)
                    if record.identity != prepared["identity"]:
                        raise relation_service.RelationConflict("Conflicting relation identity.")
            if record and (record.archived or record.withdrawn or record.superseded_by_id):
                raise relation_service.RelationConflict("Inactive identities require their explicit recovery workflow.")
            relation_service._ensure_source_open(
                prepared["schema"].relation_type_id, prepared["country"], prepared["source_version_digest"]
            )
            if prepared["schema"].relation_type_id == "plant_protection_application":
                from .applications import build_details

                _, prepared["payload"] = build_details(
                    prepared["payload"], prepared["source"], prepared["country"], prepared["participants"]
                )
            content = prepared_content(prepared)
            if identity in identities:
                previous = identities[identity]
                if digest(previous["content"]) != digest(content):
                    raise relation_service.RelationConflict("Conflicting content for the same identity in this batch.")
                return (
                    {"key": item["key"], "effect": "noop", "duplicate_of": previous["key"]},
                    set(),
                    set(),
                    {prepared["schema"].pk},
                )
            identities[identity] = {"key": item["key"], "content": content}
            ids = {pk for ids in prepared["participants"].values() for pk in ids}
            row = {"key": item["key"], "effect": "create", "after": content}
            record_ids = set()
            if record:
                latest = record.revisions.select_related("schema").order_by("-number").first()
                before = draft_content(latest) if latest else None
                row.update(record_id=str(record.pk), if_match=record_etag(record), before=before)
                record_ids.add(record.pk)
                if before is not None and digest(before) == digest(content):
                    row.update(effect="noop", revision_id=str(latest.pk))
                elif "record_id" in item:
                    row["effect"] = "revise"
                else:
                    raise relation_service.RelationConflict(
                        "Existing content differs. Select an explicit revision with If-Match.", code="source_conflict"
                    )
            return row, ids, record_ids, {prepared["schema"].pk}
        record = self.record(item["record_id"], grant)
        self.lifecycle(operation, item, validate_only=True)
        revision = record.revisions.select_related("schema").filter(pk=item.get("revision_id")).first()
        release = record.releases.filter(site_id=self.access.site_id).first()
        row = {
            "key": item["key"],
            "effect": operation,
            "record_id": str(record.pk),
            "if_match": record_etag(record),
            "before": {
                "archived": record.archived,
                "withdrawn": record.withdrawn,
                "revision": draft_content(revision) if revision else None,
                "revision_state": revision.state if revision else None,
                "released_revision_id": str(release.approved_revision_id) if release else None,
                "release_enabled": release.enabled if release else False,
            },
        }
        row["after"] = {
            "submit": {"revision_state": "submitted"},
            "approve": {"revision_state": "approved"},
            "reject": {"revision_state": "rejected"},
            "publish": {"release_enabled": True, "revision_id": item.get("revision_id")},
            "unpublish": {"release_enabled": False},
            "archive": {"archived": True, "releases_enabled": False},
        }[operation]
        if operation == "archive":
            row["before"]["releases"] = list(
                record.releases.order_by("site_id").values("site_id", "enabled", "approved_revision_id")
            )
        if (operation == "archive" and record.archived) or (
            operation == "unpublish" and release and not release.enabled
        ):
            row["effect"] = "noop"
        entity_ids = set(record.revisions.values_list("participants__entity_id", flat=True))
        schemas = set(record.revisions.values_list("schema_id", flat=True))
        return row, entity_ids, {record.pk}, schemas

    def snapshot(self, entity_ids, record_ids, schema_ids, batch):
        sites = {self.access.site_id}
        for record in RelationRecord.objects.filter(pk__in=record_ids):
            sites.update(record.releases.values_list("site_id", flat=True))
            entity_ids.update(record.revisions.values_list("participants__entity_id", flat=True))
        grants = RelationEntityGrant.objects.filter(
            grant__actor=self.access.actor, grant__site_id__in=sites, entity_id__in=entity_ids
        )
        locales = {item.get("content_locale") for item in batch["items"] if item.get("content_locale")}
        selections = EntityPresentationSelection.objects.filter(
            site_id__in=sites, entity_id__in=entity_ids, content_locale__in=locales
        )
        post_ids = set(grants.exclude(post=None).values_list("post_id", flat=True)) | set(
            selections.exclude(post=None).values_list("post_id", flat=True)
        )
        category_ids = set(grants.exclude(category=None).values_list("category_id", flat=True)) | set(
            selections.exclude(category=None).values_list("category_id", flat=True)
        )
        posts = list(Post.objects.filter(pk__in=post_ids).order_by("pk"))
        category_ids.update(post.rubric_id for post in posts)
        for category in Category.objects.filter(pk__in=category_ids):
            category_ids.update(category.get_ancestors(include_self=True).values_list("pk", flat=True))

        countries = set(RelationRevision.objects.filter(record_id__in=record_ids).values_list("country", flat=True))
        methods = set(
            PlantProtectionApplicationDetails.objects.filter(revision__record_id__in=record_ids).values_list(
                "method_id", flat=True
            )
        )
        for item in batch["items"]:
            data = item.get("draft", {})
            payload = data.get("payload", {})
            if data.get("type_code") == "plant_protection_application" and isinstance(payload, dict):
                if isinstance(payload.get("country"), str):
                    countries.add(payload["country"])
                if isinstance(payload.get("method"), str):
                    methods.add(payload["method"])

        def rows(query):
            return list(query.order_by("pk").values())

        return digest(
            {
                "entities": rows(CatalogEntity.objects.filter(pk__in=entity_ids)),
                "grants": rows(grants),
                "site_grants": rows(RelationSiteGrant.objects.filter(actor=self.access.actor, site_id__in=sites)),
                "posts": [
                    {
                        "id": post.pk,
                        "entity": post.entity_id,
                        "title": post.title,
                        "category": post.rubric_id,
                        "active": post.status,
                        "publish_date": post.publish_date,
                        "canonical": post.absolute_url,
                        "material": material_digest(post),
                    }
                    for post in posts
                ],
                "categories": rows(Category.objects.filter(pk__in=category_ids)),
                "selections": rows(selections),
                "site_policy": rows(
                    SiteContentPolicy.objects.filter(site_id__in=sites) if locales else SiteContentPolicy.objects.none()
                ),
                "category_config": rows(
                    SiteCategoryConfiguration.objects.filter(
                        site_id__in=sites, category_id__in=category_ids, content_locale__in=locales
                    )
                ),
                "publications": rows(
                    SitePostPublication.objects.filter(
                        site_id__in=sites, post_id__in=post_ids, content_locale__in=locales
                    )
                ),
                "records": rows(RelationRecord.objects.filter(pk__in=record_ids)),
                "revisions": rows(RelationRevision.objects.filter(record_id__in=record_ids)),
                "schemas": rows(RelationTypeVersion.objects.filter(pk__in=schema_ids)),
                "country_policy": rows(ApplicationCountryPolicy.objects.filter(country__in=countries)),
                "reviewer_grants": rows(
                    ApplicationReviewerGrant.objects.filter(
                        site_grant__actor=self.access.actor, site_grant__site_id__in=sites
                    )
                ),
                "methods": rows(ApplicationMethod.objects.filter(pk__in=methods)),
            }
        )

    def plan(self, batch):
        self.authorize_batch(batch)
        if batch["operation"] in {"withdraw_source", "reconcile_source"}:
            from .bulk_source import SourceBatch

            return SourceBatch(self.access).plan(batch)
        type_codes = {item["draft"]["type_code"] for item in batch["items"] if "draft" in item}
        type_codes.update(
            RelationRecord.objects.filter(
                pk__in=[item["record_id"] for item in batch["items"] if "record_id" in item]
            ).values_list("relation_type_id", flat=True)
        )
        list(RelationType.objects.select_for_update().filter(pk__in=type_codes).order_by("pk"))
        planned, entity_ids, record_ids, schema_ids, identities = [], set(), set(), set(), {}
        for item in batch["items"]:
            try:
                row, entities, records, schemas = self.plan_item(batch, item, identities)
                entity_ids.update(entities)
                record_ids.update(records)
                schema_ids.update(schemas)
            except (ValidationError, PermissionDenied, Http404) as exc:
                code = getattr(exc, "code", None) or (
                    "permission_denied"
                    if isinstance(exc, PermissionDenied)
                    else "not_found" if isinstance(exc, Http404) else "validation_error"
                )
                row = {
                    "key": item["key"],
                    "effect": "error",
                    "error": {"code": code, "detail": exc.messages if isinstance(exc, ValidationError) else [str(exc)]},
                }
            planned.append(row)
        labels = {}
        for grant in (
            self.access.participants().select_related("entity", "post", "category").filter(entity_id__in=entity_ids)
        ):
            labels[str(grant.entity_id)] = {
                "kind": grant.entity.kind,
                "label": (
                    grant.post.title
                    if grant.post_id
                    else grant.category.value if grant.category_id else str(grant.entity_id)
                ),
            }
        return {
            "items": planned,
            "participants": labels,
            "state_digest": self.snapshot(entity_ids, record_ids, schema_ids, batch),
            "can_apply": not any(row["effect"] == "error" for row in planned),
        }

    @transaction.atomic
    def preview(self, payload):
        batch = normalize_batch(payload)
        lock_publication_graph()
        self.refresh_authority()
        plan = self.plan(batch)
        payload_digest = digest(batch)
        token = signing.dumps(
            {
                "actor": self.access.actor.pk,
                "site": self.access.site_id,
                "batch": batch,
                "payload_digest": payload_digest,
                "plan_digest": digest(plan),
            },
            salt=SALT,
            compress=True,
        )
        return {
            "version": 1,
            "operation_key": batch["operation_key"],
            "operation": batch["operation"],
            "payload_digest": payload_digest,
            "preview": token,
            "expires_in": getattr(settings, "CATALOG_BATCH_PREVIEW_MAX_AGE", 900),
            **plan,
        }

    def authorize_receipt(self, result):
        operation = result["operation"]
        if operation in {"withdraw_source", "reconcile_source"}:
            from .bulk_source import SourceBatch

            SourceBatch(self.access).authorize_receipt(result)
            return
        if operation == "drafts" and result.get("requires_add", False):
            self.authorize(operation)
        self.authorize(operation, revise=result.get("requires_change", False))
        for record_id in result["record_ids"]:
            grant = self.authorize(operation, revise=result.get("requires_change", False))
            self.access._require_record(grant, record_id)
            record = RelationRecord.objects.get(pk=record_id)
            if operation in {"approve", "reject"} and record.relation_type_id == "plant_protection_application":
                from .applications import require_reviewer

                require_reviewer(self.access, record.revisions.order_by("-number").first())
            if operation == "archive":
                for site in record.releases.values_list("site_id", flat=True):
                    RelationAccess(self.access.actor, site)._grant(
                        permission="publish_relationrecord", write=True, capability="can_publish"
                    )

    @transaction.atomic
    def apply(self, token, payload_digest):
        try:
            signed = signing.loads(token, salt=SALT)
        except signing.BadSignature as exc:
            raise ValidationError("Invalid preview signature.") from exc
        if str(signed.get("actor")) != str(self.access.actor.pk) or signed.get("site") != self.access.site_id:
            raise PermissionDenied("Preview belongs to another actor or site.")
        batch = normalize_batch(signed["batch"])
        if payload_digest != signed["payload_digest"] or digest(batch) != payload_digest:
            raise relation_service.RelationConflict("Preview payload digest changed.", code="stale_preview")
        lock_publication_graph()
        self.refresh_authority()
        self.authorize_batch(batch)
        receipt = ImportReceipt.objects.filter(actor_scope=self.scope, operation_key=batch["operation_key"]).first()
        if receipt:
            if receipt.request_digest != payload_digest:
                raise relation_service.RelationConflict(
                    "Operation key already used with different input.", code="idempotency_conflict"
                )
            self.authorize_receipt(receipt.result)
            return receipt, True
        try:
            signing.loads(token, salt=SALT, max_age=getattr(settings, "CATALOG_BATCH_PREVIEW_MAX_AGE", 900))
        except signing.SignatureExpired as exc:
            raise relation_service.RelationConflict(
                "Preview expired. Review a new preview.", code="preview_expired"
            ) from exc
        plan = self.plan(batch)
        if not plan["can_apply"]:
            raise relation_service.RelationConflict(
                "Preview contains errors. Review the corrected batch.", code="invalid_preview"
            )
        if digest(plan) != signed["plan_digest"]:
            raise relation_service.RelationConflict(
                "Preview state changed. Review a new preview.", code="stale_preview"
            )
        results, references = [], {}
        for item, row in zip(batch["items"], plan["items"], strict=True):
            if "duplicate_of" in row:
                result = {
                    **references[row["duplicate_of"]],
                    "key": item["key"],
                    "effect": "noop",
                    "duplicate_of": row["duplicate_of"],
                }
            elif row["effect"] == "noop":
                result = {
                    key: value for key, value in row.items() if key in {"key", "effect", "record_id", "revision_id"}
                }
            elif batch["operation"] in {"withdraw_source", "reconcile_source"}:
                from .bulk_source import SourceBatch

                result = SourceBatch(self.access).execute(batch)
            elif batch["operation"] == "drafts":
                record = RelationRecord.objects.get(pk=item["record_id"]) if "record_id" in item else None
                revision = self.access.save_draft(
                    **item["draft"],
                    record_id=record.pk if record else None,
                    expected_version=record.lock_version if record else None,
                )
                result = {
                    "key": item["key"],
                    "effect": row["effect"],
                    "record_id": str(revision.record_id),
                    "revision_id": str(revision.pk),
                }
            else:
                self.lifecycle(batch["operation"], item, validate_only=False)
                result = {"key": item["key"], "effect": row["effect"], "record_id": item["record_id"]}
            if "record_id" in result:
                record = RelationRecord.objects.get(pk=result["record_id"])
                result.update(etag=record_etag(record), archived=record.archived, withdrawn=record.withdrawn)
            results.append(result)
            references[item["key"]] = result
        result = {
            "version": 1,
            "operation": batch["operation"],
            "operation_key": batch["operation_key"],
            "actor_id": self.access.actor.pk,
            "site_id": self.access.site_id,
            "payload_digest": payload_digest,
            "completed_at": timezone.now().isoformat(),
            "items": results,
            "requires_change": any("record_id" in item for item in batch["items"]),
            "requires_add": any("record_id" not in item for item in batch["items"]),
            "record_ids": sorted(
                {row["record_id"] for row in results if "record_id" in row}
                | {pk for row in results for pk in row.get("record_ids", [])}
            ),
        }
        if batch["operation"] in {"withdraw_source", "reconcile_source"}:
            result["source_context"] = {
                key: value
                for key, value in batch["items"][0].items()
                if key in {"country", "type_code", "scope_complete"}
            }
        receipt = ImportReceipt.objects.create(
            actor_scope=self.scope, operation_key=batch["operation_key"], request_digest=payload_digest, result=result
        )
        return receipt, False

    @transaction.atomic
    def receipt(self, receipt_id):
        lock_publication_graph()
        self.refresh_authority()
        receipt = ImportReceipt.objects.filter(pk=receipt_id, actor_scope=self.scope).first()
        if receipt is None:
            raise Http404("Batch receipt is unavailable.")
        self.authorize_receipt(receipt.result)
        return receipt


CURSOR_SALT = "catalog-batch-results-v1"


def receipt_page(receipt, *, cursor=None, page_size=20):
    if not isinstance(page_size, int) or isinstance(page_size, bool) or not 1 <= page_size <= 50:
        raise ValidationError("Invalid receipt page size.")
    last = ""
    if cursor:
        try:
            value = signing.loads(cursor, salt=CURSOR_SALT)
        except signing.BadSignature as exc:
            raise ValidationError("Invalid batch results cursor.") from exc
        if value.get("receipt") != receipt.pk or not isinstance(value.get("key"), str):
            raise ValidationError("Cursor belongs to another batch receipt.")
        last = value["key"]
    result = receipt.result
    remaining = [row for row in result["items"] if row["key"] > last]
    rows = remaining[:page_size]
    next_cursor = (
        signing.dumps({"receipt": receipt.pk, "key": rows[-1]["key"]}, salt=CURSOR_SALT)
        if len(remaining) > page_size
        else None
    )
    body = {
        key: result[key]
        for key in ("version", "operation", "operation_key", "actor_id", "site_id", "payload_digest", "completed_at")
    }
    body.update(receipt_id=receipt.pk, count=len(result["items"]), results=rows)
    return body, next_cursor
