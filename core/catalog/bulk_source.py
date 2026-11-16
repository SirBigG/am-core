"""Application source batches over the shared withdrawal/quarantine service."""

import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError

from . import relation_service
from .access_models import PrivateRelationSite, RelationEntityGrant, RelationSiteGrant
from .application_models import ApplicationReviewerGrant
from .applications import APPLICATION_TYPE, require_country_reviewer
from .bulk import MAX_ITEMS, digest, record_etag
from .relation_access import RelationAccess
from .relations import RelationRecord, RelationRevision, RelationScopeGate, RelationType, SourceWithdrawalGate

SOURCE_OPERATIONS = {"withdraw_source", "reconcile_source"}


def manifest(value):
    if not isinstance(value, dict) or len(value) > MAX_ITEMS:
        raise ValidationError("A source manifest is a bounded record UUID/version object.")
    result = {}
    for key, version in value.items():
        try:
            key = str(UUID(key))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValidationError("Invalid source manifest record UUID.") from exc
        if (
            not isinstance(version, int)
            or isinstance(version, bool)
            or not 1 <= version <= 9223372036854775807
            or key in result
        ):
            raise ValidationError("Source manifest versions must be positive integers with unique record UUIDs.")
        result[key] = version
    return result


def normalize_source_batch(operation, key, items):
    if len(items) != 1 or not isinstance(items[0], dict):
        raise ValidationError("Select one source withdrawal or reconciliation per atomic batch.")
    item = items[0]
    fields = {"key", "type_code", "country", "affected_versions", "evidence"}
    fields |= (
        {"source_version_digest", "reason", "scope_complete", "scope_versions"}
        if operation == "withdraw_source"
        else {"if_match"}
    )
    if (
        set(item) != fields
        or not isinstance(item["key"], str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", item["key"]) is None
    ):
        raise ValidationError("Source batch fields and item key must match the documented operation.")
    if (
        item["type_code"] != APPLICATION_TYPE
        or not isinstance(item["country"], str)
        or re.fullmatch(r"[A-Z]{2}", item["country"]) is None
    ):
        raise ValidationError("An application domain adapter and explicit country are required.")
    if not isinstance(item["evidence"], dict) or not item["evidence"]:
        raise ValidationError("Source operations require structured reviewed evidence.")
    item = {**item, "affected_versions": manifest(item["affected_versions"])}
    if operation == "withdraw_source":
        if (
            not isinstance(item["source_version_digest"], str)
            or re.fullmatch(r"[a-f0-9]{64}", item["source_version_digest"]) is None
        ):
            raise ValidationError("Use the canonical source-version digest from the revision.")
        if (
            not isinstance(item["reason"], str)
            or not item["reason"].strip()
            or len(item["reason"]) > 2000
            or not isinstance(item["scope_complete"], bool)
        ):
            raise ValidationError("Source withdrawal requires a reason and explicit scope_complete boolean.")
        item["scope_versions"] = manifest(item["scope_versions"])
        if item["scope_complete"] and item["scope_versions"]:
            raise ValidationError("A complete source scope has no separate quarantine manifest.")
    elif not isinstance(item["if_match"], str):
        raise ValidationError("Reconciliation requires the current scope ETag.")
    return {"operation": operation, "operation_key": key, "items": [item]}


class SourceBatch:
    def __init__(self, access):
        self.access = access

    def authority(self, item, record_ids, *, platform):
        self.access._grant(permission="withdraw_relation", write=True, capability="can_review")
        require_country_reviewer(self.access, item["country"])
        self.access._grant(permission="publish_relationrecord", write=True, capability="can_publish")
        sites = set(PrivateRelationSite.objects.filter(record_id__in=record_ids).values_list("site_id", flat=True)) | {
            self.access.site_id
        }
        for record in RelationRecord.objects.filter(pk__in=record_ids):
            sites.update(record.releases.values_list("site_id", flat=True))
        if (platform or len(sites) > 1) and not self.access.actor.has_perm("catalog.review_shared_relations"):
            raise PermissionDenied("Source reconciliation/quarantine requires platform authority.")
        for record_id in sorted(record_ids):
            binding = PrivateRelationSite.objects.filter(record_id=record_id).first()
            if binding is None:
                raise PermissionDenied("The complete source scope is unavailable.")
            RelationAccess(self.access.actor, binding.site_id)._application_global_authority(
                record_id=record_id, permission="withdraw_relation"
            )

    def context(self, operation, item):
        RelationType.objects.select_for_update().get(pk=APPLICATION_TYPE)
        country_records = RelationRecord.objects.filter(
            relation_type_id=APPLICATION_TYPE,
            pk__in=RelationRevision.objects.filter(country=item["country"]).values("record_id"),
        )
        scope = (
            RelationScopeGate.objects.select_for_update()
            .filter(relation_type_id=APPLICATION_TYPE, country=item["country"])
            .first()
        )
        if operation == "withdraw_source":
            source_ids = RelationRevision.objects.filter(
                country=item["country"], source_version_digest=item["source_version_digest"]
            ).values("record_id")
            selected = country_records.filter(pk__in=source_ids)
            quarantine = (
                country_records.filter(
                    releases__enabled=True, releases__approved_revision__country=item["country"]
                ).distinct()
                if not item["scope_complete"]
                else country_records.none()
            )
        else:
            selected, quarantine = country_records, country_records.none()
        records = list(RelationRecord.objects.select_for_update().filter(pk__in=selected.values("pk")).order_by("pk"))
        quarantined = list(
            RelationRecord.objects.select_for_update().filter(pk__in=quarantine.values("pk")).order_by("pk")
        )
        ids = {record.pk for record in records + quarantined}
        self.authority(item, ids, platform=operation == "reconcile_source" or not item["scope_complete"])
        if len(ids) > MAX_ITEMS:
            raise ValidationError("The atomic source scope exceeds the 50-record batch limit.")
        return records, quarantined, scope

    def plan(self, batch):
        operation, item = batch["operation"], batch["items"][0]
        records, quarantine, scope = self.context(operation, item)
        actual = {str(record.pk): record.lock_version for record in records}
        quarantine_versions = {str(record.pk): record.lock_version for record in quarantine}
        row = {
            "key": item["key"],
            "effect": operation,
            "affected_versions": actual,
            "scope_versions": quarantine_versions,
            "records": [
                {"record_id": str(record.pk), "if_match": record_etag(record), "withdrawn": record.withdrawn}
                for record in records
            ],
            "after": {"releases_enabled": False, "source_stays_blocked": True},
        }
        source_ids = {record.pk for record in records}
        quarantine_ids = {record.pk for record in quarantine}
        all_records = {record.pk: record for record in records + quarantine}
        row["before"] = {
            "records": [
                {
                    "record_id": str(record.pk),
                    "version": record.lock_version,
                    "withdrawn": record.withdrawn,
                    "epoch": record.eligibility_epoch,
                    "releases": list(
                        record.releases.order_by("site_id").values("site_id", "enabled", "approved_revision_id")
                    ),
                }
                for record in sorted(all_records.values(), key=lambda record: record.pk)
            ]
        }
        row["after"]["scope_quarantined"] = (
            (not item["scope_complete"] or bool(scope and scope.quarantined))
            if operation == "withdraw_source"
            else False
        )
        row["after"]["records"] = [
            {
                "record_id": str(record.pk),
                "version": record.lock_version
                + (
                    int(record.pk in quarantine_ids) + int(record.pk in source_ids)
                    if operation == "withdraw_source"
                    else 0
                ),
                "withdrawn": True if operation == "withdraw_source" and record.pk in source_ids else record.withdrawn,
                "epoch": record.eligibility_epoch + int(operation == "withdraw_source" and record.pk in source_ids),
                "releases_enabled": False,
            }
            for record in sorted(all_records.values(), key=lambda record: record.pk)
        ]
        error = None
        if actual != item["affected_versions"] or (
            operation == "withdraw_source" and quarantine_versions != item["scope_versions"]
        ):
            error = "The selected source/quarantine manifest changed. Review and select its exact current records."
        elif operation == "withdraw_source":
            if SourceWithdrawalGate.objects.filter(
                relation_type_id=APPLICATION_TYPE,
                country=item["country"],
                source_version_digest=item["source_version_digest"],
            ).exists():
                error = "This source version is already withdrawn. Read its completed batch receipt."
            elif not item["scope_complete"] and scope and scope.quarantined:
                error = "This country scope already has an unresolved quarantine."
        else:
            row["current_scope_etag"] = (
                f'"source-scope:{APPLICATION_TYPE}:{item["country"]}:{scope.lock_version}"' if scope else None
            )
            if scope is None or not scope.quarantined:
                error = "Source scope is unavailable or already reconciled."
            elif item["if_match"] != row["current_scope_etag"]:
                error = "The source scope ETag changed. Review a new preview."
        if error:
            row.update(effect="error", error={"code": "stale_manifest", "detail": [error]})
        ids = {record.pk for record in records + quarantine}
        sites = set(PrivateRelationSite.objects.filter(record_id__in=ids).values_list("site_id", flat=True)) | {
            self.access.site_id
        }
        for record in records + quarantine:
            sites.update(record.releases.values_list("site_id", flat=True))
        entities = set(
            RelationRevision.objects.filter(record_id__in=ids).values_list("participants__entity_id", flat=True)
        )
        gates = SourceWithdrawalGate.objects.filter(relation_type_id=APPLICATION_TYPE, country=item["country"])
        if operation == "withdraw_source":
            gates = gates.filter(source_version_digest=item["source_version_digest"])
        state = {
            "records": list(RelationRecord.objects.filter(pk__in=ids).order_by("pk").values()),
            "source_gates": list(gates.order_by("pk").values()),
            "scope": list(
                RelationScopeGate.objects.filter(relation_type_id=APPLICATION_TYPE, country=item["country"]).values()
            ),
            "site_grants": list(
                RelationSiteGrant.objects.filter(actor=self.access.actor, site_id__in=sites).order_by("pk").values()
            ),
            "entity_grants": list(
                RelationEntityGrant.objects.filter(
                    grant__actor=self.access.actor, grant__site_id__in=sites, entity_id__in=entities
                )
                .order_by("pk")
                .values()
            ),
            "review_grants": list(
                ApplicationReviewerGrant.objects.filter(
                    site_grant__actor=self.access.actor, site_grant__site_id__in=sites, country_id=item["country"]
                )
                .order_by("pk")
                .values()
            ),
        }
        return {"items": [row], "participants": {}, "state_digest": digest(state), "can_apply": error is None}

    def execute(self, batch):
        operation, item = batch["operation"], batch["items"][0]
        records, quarantine, scope = self.context(operation, item)
        if operation == "withdraw_source":
            gate = relation_service.withdraw_source(
                type_code=APPLICATION_TYPE,
                country=item["country"],
                digest=item["source_version_digest"],
                reason=item["reason"],
                evidence=item["evidence"],
                actor=self.access.actor,
                affected_versions=item["affected_versions"],
                scope_complete=item["scope_complete"],
            )
            scope = RelationScopeGate.objects.filter(relation_type_id=APPLICATION_TYPE, country=item["country"]).first()
            reference = {"source_gate_id": gate.pk}
        else:
            scope = relation_service.reconcile_source_scope(
                type_code=APPLICATION_TYPE,
                country=item["country"],
                expected_version=scope.lock_version,
                actor=self.access.actor,
                evidence=item["evidence"],
            )
            reference = {"scope_id": scope.pk}
        return {
            "key": item["key"],
            "effect": operation,
            "record_ids": sorted({str(record.pk) for record in records + quarantine}),
            "scope_quarantined": scope.quarantined if scope else False,
            "scope_etag": (
                f'"source-scope:{APPLICATION_TYPE}:{item["country"]}:{scope.lock_version}"' if scope else None
            ),
            **reference,
        }

    def authorize_receipt(self, result):
        item = result["source_context"]
        self.authority(
            item,
            result["record_ids"],
            platform=result["operation"] == "reconcile_source" or not item.get("scope_complete", True),
        )
