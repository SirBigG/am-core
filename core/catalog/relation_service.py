"""Storage operations for trusted catalog writers.

Callers in Admin and API own authorization, site policy and source
certification.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import F, Max
from django.utils import timezone

from .applications import APPLICATION_TYPE, build_details, source_scope
from .models import CatalogEntity, CatalogEntityState
from .relations import (
    EntityPresentationSelection,
    ImportReceipt,
    RelationAuditEvent,
    RelationIdentityCorrection,
    RelationParticipant,
    RelationRecord,
    RelationRelease,
    RelationRevision,
    RelationScopeGate,
    RelationType,
    RelationTypeVersion,
    RelationWithdrawal,
    ReviewState,
    SourceWithdrawalGate,
)
from .validation import validate_database_text


class RelationConflict(ValidationError):
    pass


def _expect_version(record, expected_version):
    if expected_version != record.lock_version:
        raise RelationConflict("Record version changed.", code="stale_version")


def _audit(record, action, actor, *, revision=None, base_version=None, result=None):
    RelationAuditEvent.objects.create(
        record=record,
        action=action,
        actor=actor,
        revision=revision,
        base_version=base_version,
        source_digest=revision.source_version_digest if revision else "",
        result=result or {},
    )


def _lock_record(record_id, expected_version):
    type_code = RelationRecord.objects.values_list("relation_type_id", flat=True).get(pk=record_id)
    RelationType.objects.select_for_update().get(pk=type_code)
    record = RelationRecord.objects.select_for_update().get(pk=record_id)
    _expect_version(record, expected_version)
    return record


def _validate_source(country, digest):
    if not (country == digest == "" or (re.fullmatch(r"[A-Z]{2}", country) and re.fullmatch(r"[a-f0-9]{64}", digest))):
        raise ValidationError("Country and canonical source-version digest must be supplied together.")


def _ensure_source_open(type_code, country, digest):
    if (
        SourceWithdrawalGate.objects.filter(
            relation_type_id=type_code, country=country, source_version_digest=digest
        ).exists()
        or RelationScopeGate.objects.filter(relation_type_id=type_code, country=country, quarantined=True).exists()
    ):
        raise RelationConflict("Source version or relation scope is unavailable.", code="source_withdrawn")


def _participants(schema, participants):
    if not isinstance(participants, Mapping):
        raise ValidationError("Participants must be grouped by role.")
    if set(participants) - set(schema.roles):
        raise ValidationError("Unknown relation role.")
    try:
        grouped = {role: sorted(UUID(str(pk)) for pk in ids) for role, ids in participants.items()}
    except (ValueError, TypeError) as exc:
        raise ValidationError("Participants must contain entity UUIDs.") from exc
    all_ids = [pk for ids in grouped.values() for pk in ids]
    if len(set(all_ids)) != len(all_ids):
        raise ValidationError("Repeated participants are not allowed.")
    entities = {
        entity.pk: entity for entity in CatalogEntity.objects.select_for_update().filter(pk__in=all_ids).order_by("pk")
    }
    for role, rule in schema.roles.items():
        ids = grouped.get(role, ())
        if not rule["min"] <= len(ids) <= rule["max"]:
            raise ValidationError(f"Incorrect participant count for {role}.")
        for pk in ids:
            entity = entities.get(pk)
            if entity is None or entity.kind not in rule["kinds"] or entity.state != CatalogEntityState.ACTIVE:
                raise ValidationError(f"Unavailable participant for {role}.")
    return grouped


def _identity(schema, grouped, payload):
    identity = {
        "roles": {role: [str(pk) for pk in grouped[role]] for role in schema.identity_roles if grouped.get(role)},
        "fields": {field: payload.get(field) for field in schema.identity_fields},
    }
    with connection.cursor() as cursor:
        cursor.execute("SELECT catalog_identity_digest(%s::jsonb)", [json.dumps(identity, allow_nan=False)])
        digest = cursor.fetchone()[0]
    return identity, digest


def _new_revision(record, schema, grouped, payload, source, country, digest, actor):
    if record.archived or record.superseded_by_id:
        raise RelationConflict("Archived or superseded records cannot be edited.")
    _ensure_source_open(record.relation_type_id, country, digest)
    number = (record.revisions.aggregate(last=Max("number"))["last"] or 0) + 1
    base = (
        record.revisions.filter(state=ReviewState.APPROVED, approval_epoch=record.eligibility_epoch)
        .order_by("-number")
        .first()
    )
    application = None
    if schema.relation_type_id == APPLICATION_TYPE:
        application, payload = build_details(payload, source, country, grouped)
    revision = RelationRevision.objects.create(
        record=record,
        schema=schema,
        number=number,
        payload=payload,
        source=source,
        country=country,
        source_version_digest=digest,
        created_epoch=record.eligibility_epoch,
        base_approved_revision=base,
        created_by=actor,
    )
    RelationParticipant.objects.bulk_create(
        [
            RelationParticipant(revision=revision, role=role, entity_id=pk, ordinal=ordinal)
            for role, ids in grouped.items()
            for ordinal, pk in enumerate(ids)
        ]
    )
    if application is not None:
        application.revision = revision
        application.save()
    revision.sealed = True
    revision.save(update_fields=["sealed"])
    base_version = record.lock_version
    record.lock_version += 1
    record.save(update_fields=["lock_version"])
    _audit(record, "draft", actor, revision=revision, base_version=base_version)
    return revision


def prepare_draft(
    *, type_code, schema_version, participants, payload=None, source=None, country="", source_version_digest=""
):
    """Validate shared identity/source input without inserting a record or
    revision."""
    payload = {} if payload is None else payload
    source = {} if source is None else source
    if not isinstance(payload, dict) or not isinstance(source, dict):
        raise ValidationError("Payload and source must be JSON objects.")
    validate_database_text(payload)
    validate_database_text(source)
    if not isinstance(country, str) or not isinstance(source_version_digest, str):
        raise ValidationError("Country and source digest must be strings.")
    if type_code == APPLICATION_TYPE:
        country, source_version_digest = source_scope(payload, source, country, source_version_digest)
    _validate_source(country, source_version_digest)
    relation_type = RelationType.objects.select_for_update().filter(pk=type_code).first()
    schema = RelationTypeVersion.objects.filter(relation_type=relation_type, version=schema_version).first()
    if relation_type is None or schema is None:
        raise ValidationError("Relation type or schema is unavailable.")
    grouped = _participants(schema, participants)
    identity, digest = _identity(schema, grouped, payload)
    return {
        "schema": schema,
        "participants": grouped,
        "payload": payload,
        "source": source,
        "country": country,
        "source_version_digest": source_version_digest,
        "identity": identity,
        "identity_digest": digest,
    }


@transaction.atomic
def save_draft(
    *,
    type_code,
    schema_version,
    participants,
    actor,
    payload=None,
    source=None,
    country="",
    source_version_digest="",
    record_id=None,
    expected_version=None,
):
    """Create a record or append an immutable draft under a matching
    identity."""
    prepared = prepare_draft(
        type_code=type_code,
        schema_version=schema_version,
        participants=participants,
        payload=payload,
        source=source,
        country=country,
        source_version_digest=source_version_digest,
    )
    schema, grouped = prepared["schema"], prepared["participants"]
    payload, source = prepared["payload"], prepared["source"]
    country, source_version_digest = prepared["country"], prepared["source_version_digest"]
    identity, digest = prepared["identity"], prepared["identity_digest"]
    relation_type = schema.relation_type
    if record_id is None:
        record, created = RelationRecord.objects.get_or_create(
            relation_type=relation_type, identity_digest=digest, defaults={"identity": identity, "created_by": actor}
        )
        if not created:
            if record.identity != identity:
                raise RelationConflict("Semantic identity digest collision.")
            raise RelationConflict("Relation already exists.", code="duplicate_relation")
    else:
        record = RelationRecord.objects.select_for_update().get(pk=record_id, relation_type=relation_type)
        _expect_version(record, expected_version)
        if record.identity_digest != digest or record.identity != identity:
            raise RelationConflict("Use identity correction.", code="identity_change_requires_correction")
    return _new_revision(record, schema, grouped, payload, source, country, source_version_digest, actor)


@transaction.atomic
def review_revision(*, record_id, revision_id, expected_version, action, actor, validate_only=False):
    transitions = {
        ("draft", "submit"): ReviewState.SUBMITTED,
        ("submitted", "approve"): ReviewState.APPROVED,
        ("submitted", "reject"): ReviewState.REJECTED,
    }
    record = _lock_record(record_id, expected_version)
    revision = record.revisions.select_for_update().get(pk=revision_id)
    target = transitions.get((revision.state, action))
    if not target or record.archived or record.superseded_by_id or revision.created_epoch != record.eligibility_epoch:
        raise RelationConflict("Invalid or stale review transition.")
    _ensure_source_open(record.relation_type_id, revision.country, revision.source_version_digest)
    if revision.participants.exclude(entity__state=CatalogEntityState.ACTIVE).exists():
        raise ValidationError("All participants must remain active.")
    if target == ReviewState.APPROVED:
        current = (
            record.revisions.filter(state=ReviewState.APPROVED, approval_epoch=record.eligibility_epoch)
            .order_by("-number")
            .first()
        )
        if revision.base_approved_revision_id != (current.pk if current else None):
            raise RelationConflict("Approved base revision changed.", code="stale_base")
    if validate_only:
        return revision
    if target == ReviewState.APPROVED:
        revision.approval_epoch = record.eligibility_epoch
    if target in {ReviewState.APPROVED, ReviewState.REJECTED}:
        revision.reviewed_by = actor
        revision.reviewed_at = timezone.now()
    revision.state = target
    revision.save(update_fields=["state", "approval_epoch", "reviewed_by", "reviewed_at"])
    record.lock_version += 1
    record.save(update_fields=["lock_version"])
    _audit(record, action, actor, revision=revision, base_version=expected_version)
    return revision


@transaction.atomic
def set_release(*, record_id, revision_id, site, expected_version, actor, enabled, validate_only=False):
    record = _lock_record(record_id, expected_version)
    revision = record.revisions.get(pk=revision_id, state=ReviewState.APPROVED)
    if enabled:
        if (
            record.archived
            or record.withdrawn
            or record.superseded_by_id
            or (revision.approval_epoch != record.eligibility_epoch)
        ):
            raise RelationConflict("Revision is ineligible for release.")
        _ensure_source_open(record.relation_type_id, revision.country, revision.source_version_digest)
        if revision.participants.exclude(entity__state=CatalogEntityState.ACTIVE).exists():
            raise ValidationError("All participants must remain active.")
    release = RelationRelease.objects.select_for_update().filter(site=site, record=record).first()
    if validate_only:
        if not enabled and (release is None or release.approved_revision_id != revision.pk):
            raise RelationConflict("Requested release pointer does not exist.")
        return release
    if enabled and release is None:
        release = RelationRelease.objects.create(site=site, record=record, approved_revision=revision, enabled=True)
    elif release is None or (not enabled and release.approved_revision_id != revision.pk):
        raise RelationConflict("Requested release pointer does not exist.")
    else:
        release.approved_revision = revision
        release.enabled = enabled
        release.lock_version += 1
        release.save(update_fields=["approved_revision", "enabled", "lock_version"])
    record.lock_version += 1
    record.save(update_fields=["lock_version"])
    _audit(
        record,
        "release" if enabled else "unrelease",
        actor,
        revision=revision,
        base_version=expected_version,
        result={"site_ids": [site.pk]},
    )
    return release


def _disable_releases(record):
    sites = list(record.releases.filter(enabled=True).order_by("site_id").values_list("site_id", flat=True))
    record.releases.filter(enabled=True).update(enabled=False, lock_version=F("lock_version") + 1)
    return sites


def _withdraw(record, *, actor, reason, evidence):
    if not reason.strip() or not evidence:
        raise ValidationError("Withdrawal needs reason and evidence.")
    sites = _disable_releases(record)
    base = record.lock_version
    record.withdrawn = True
    record.eligibility_epoch += 1
    record.lock_version += 1
    record.save(update_fields=["withdrawn", "eligibility_epoch", "lock_version"])
    withdrawal = RelationWithdrawal.objects.create(
        record=record,
        resulting_epoch=record.eligibility_epoch,
        reason=reason,
        evidence=evidence,
        affected_site_ids=sites,
        actor=actor,
    )
    _audit(record, "withdraw", actor, base_version=base, result={"site_ids": sites, "withdrawal": str(withdrawal.pk)})
    return withdrawal


@transaction.atomic
def withdraw_record(*, record_id, expected_version, actor, reason, evidence, operation_key):
    if not operation_key or len(operation_key) > 128:
        raise ValidationError("Withdrawal requires an operation key.")
    type_code = RelationRecord.objects.values_list("relation_type_id", flat=True).get(pk=record_id)
    RelationType.objects.select_for_update().get(pk=type_code)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "record": str(record_id),
                "version": expected_version,
                "reason": reason,
                "evidence": evidence,
            },
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    scope = f"withdraw:{type_code}:{actor.pk}"
    receipt = ImportReceipt.objects.filter(actor_scope=scope, operation_key=operation_key).first()
    if receipt:
        if receipt.request_digest != fingerprint:
            raise RelationConflict("Operation key already used with different input.")
        return RelationWithdrawal.objects.get(pk=receipt.result["withdrawal"])
    record = RelationRecord.objects.select_for_update().get(pk=record_id)
    _expect_version(record, expected_version)
    withdrawal = _withdraw(record, actor=actor, reason=reason, evidence=evidence)
    ImportReceipt.objects.create(
        actor_scope=scope,
        operation_key=operation_key,
        request_digest=fingerprint,
        result={"withdrawal": str(withdrawal.pk)},
    )
    return withdrawal


@transaction.atomic
def reinstate_record(*, record_id, revision_id, withdrawal_id, expected_version, actor, evidence):
    record = _lock_record(record_id, expected_version)
    revision = record.revisions.get(pk=revision_id, state=ReviewState.APPROVED)
    withdrawal = record.withdrawals.filter(resulting_epoch=record.eligibility_epoch).first()
    if (
        not record.withdrawn
        or record.superseded_by_id
        or not evidence
        or not withdrawal
        or (withdrawal.pk != withdrawal_id or revision.approval_epoch != record.eligibility_epoch)
    ):
        raise RelationConflict("Reinstatement needs current reviewed evidence and withdrawal reference.")
    _ensure_source_open(record.relation_type_id, revision.country, revision.source_version_digest)
    record.withdrawn = False
    record.lock_version += 1
    record.save(update_fields=["withdrawn", "lock_version"])
    _audit(
        record,
        "reinstate",
        actor,
        revision=revision,
        base_version=expected_version,
        result={"evidence": evidence, "withdrawal": str(withdrawal.pk)},
    )


@transaction.atomic
def archive_record(*, record_id, expected_version, actor, private_only=False, validate_only=False):
    record = _lock_record(record_id, expected_version)
    if private_only and record.releases.exists():
        raise RelationConflict("Records with a release history require the publication policy.")
    if validate_only:
        return record
    sites = _disable_releases(record)
    record.archived = True
    record.lock_version += 1
    record.save(update_fields=["archived", "lock_version"])
    _audit(record, "archive", actor, base_version=expected_version, result={"site_ids": sites})


@transaction.atomic
def correct_identity(
    *,
    record_id,
    expected_version,
    schema_version,
    participants,
    actor,
    reason,
    evidence,
    operation_key,
    payload,
    source,
    country="",
    source_version_digest="",
    authorized_target_id=None,
    target_expected_version=None,
):
    """Atomically create or reference the corrected identity and withdraw the
    original.

    A caller may reference an existing target only after authorizing
    access to that specific record.
    """
    if not operation_key or len(operation_key) > 128 or not isinstance(payload, dict) or not isinstance(source, dict):
        raise ValidationError("Correction needs an operation key and structured payload/source.")
    type_code = RelationRecord.objects.values_list("relation_type_id", flat=True).get(pk=record_id)
    if type_code == APPLICATION_TYPE:
        country, source_version_digest = source_scope(payload, source, country, source_version_digest)
    _validate_source(country, source_version_digest)
    definition = RelationType.objects.select_for_update().get(pk=type_code)
    schema = RelationTypeVersion.objects.get(relation_type=definition, version=schema_version)
    grouped = _participants(schema, participants)
    identity, digest = _identity(schema, grouped, payload)
    fingerprint = hashlib.sha256(
        json.dumps(
            {
                "record": str(record_id),
                "version": expected_version,
                "schema": schema_version,
                "participants": {role: [str(pk) for pk in ids] for role, ids in grouped.items()},
                "payload": payload,
                "source": source,
                "country": country,
                "digest": source_version_digest,
                "reason": reason,
                "evidence": evidence,
                "target": str(authorized_target_id),
                "target_version": target_expected_version,
            },
            sort_keys=True,
            allow_nan=False,
        ).encode()
    ).hexdigest()
    receipt_scope = f"correct-identity:{type_code}:{actor.pk}"
    receipt = ImportReceipt.objects.filter(actor_scope=receipt_scope, operation_key=operation_key).first()
    if receipt:
        if receipt.request_digest != fingerprint:
            raise RelationConflict("Operation key already used with different input.")
        return RelationIdentityCorrection.objects.get(pk=receipt.result["correction"])

    original = RelationRecord.objects.get(pk=record_id)
    target = RelationRecord.objects.filter(relation_type=definition, identity_digest=digest).first()
    records = {
        row.pk: row
        for row in RelationRecord.objects.select_for_update()
        .filter(pk__in=[original.pk] + ([target.pk] if target else []))
        .order_by("pk")
    }
    original = records[original.pk]
    _expect_version(original, expected_version)
    if original.superseded_by_id or original.identity == identity:
        raise RelationConflict("Correction requires an unsuperseded record and a different identity.")
    if target:
        target = records[target.pk]
        if target.identity != identity or target.pk != authorized_target_id or target.superseded_by_id:
            raise RelationConflict("Corrected identity is unavailable.")
        _expect_version(target, target_expected_version)
    else:
        target = RelationRecord.objects.create(
            relation_type=definition, identity=identity, identity_digest=digest, created_by=actor
        )
        _new_revision(target, schema, grouped, payload, source, country, source_version_digest, actor)
    withdrawal = _withdraw(original, actor=actor, reason=reason, evidence=evidence)
    original.superseded_by = target
    original.archived = True
    original.save(update_fields=["superseded_by", "archived"])
    correction = RelationIdentityCorrection.objects.create(
        original=original, successor=target, withdrawal=withdrawal, operation_key=operation_key
    )
    ImportReceipt.objects.create(
        actor_scope=receipt_scope,
        operation_key=operation_key,
        request_digest=fingerprint,
        result={"correction": correction.pk},
    )
    _audit(original, "correct-identity", actor, base_version=expected_version, result={"successor": str(target.pk)})
    return correction


@transaction.atomic
def withdraw_source(*, type_code, country, digest, reason, evidence, actor, affected_versions, scope_complete):
    """Withdraw all locally identified records of a source, with an optional
    scope quarantine."""
    _validate_source(country, digest)
    if not country or not reason.strip() or not evidence:
        raise ValidationError("A canonical source version and evidence are required.")
    definition = RelationType.objects.select_for_update().get(pk=type_code)
    records = list(
        RelationRecord.objects.select_for_update()
        .filter(
            relation_type=definition,
            pk__in=RelationRevision.objects.filter(country=country, source_version_digest=digest).values("record_id"),
        )
        .order_by("pk")
    )
    if {str(record.pk): record.lock_version for record in records} != affected_versions:
        raise RelationConflict("Affected record manifest changed.", code="stale_manifest")
    gate, created = SourceWithdrawalGate.objects.get_or_create(
        relation_type=definition,
        country=country,
        source_version_digest=digest,
        defaults={"actor": actor, "evidence": evidence},
    )
    if not created:
        raise RelationConflict("Source version is already withdrawn.")
    if not scope_complete:
        scope, created = RelationScopeGate.objects.select_for_update().get_or_create(
            relation_type=definition, country=country, defaults={"source": gate, "evidence": evidence}
        )
        if not created:
            if scope.quarantined:
                raise RelationConflict("An unresolved source quarantine already exists for this scope.")
            scope.quarantined = True
            scope.source = gate
            scope.evidence = evidence
            scope.lock_version += 1
            scope.save(update_fields=["quarantined", "source", "evidence", "lock_version"])
        # Quarantine covers the whole scope, including releases from other source versions.
        quarantined = RelationRelease.objects.filter(
            record__relation_type=definition, approved_revision__country=country, enabled=True
        )
        for record in (
            RelationRecord.objects.select_for_update().filter(pk__in=quarantined.values("record_id")).order_by("pk")
        ):
            sites = list(quarantined.filter(record=record).values_list("site_id", flat=True))
            quarantined.filter(record=record).update(enabled=False, lock_version=F("lock_version") + 1)
            record.lock_version += 1
            record.save(update_fields=["lock_version"])
            _audit(record, "quarantine", actor, result={"site_ids": sites, "source_gate": gate.pk})
    # Refresh after quarantine so counters and evidence reflect the same transaction.
    for record in records:
        record.refresh_from_db()
        _withdraw(record, actor=actor, reason=reason, evidence={"source_gate": gate.pk, "evidence": evidence})
    return gate


@transaction.atomic
def reconcile_source_scope(*, type_code, country, expected_version, actor, evidence):
    if not evidence:
        raise ValidationError("Reviewed scope reconciliation evidence is required.")
    definition = RelationType.objects.select_for_update().get(pk=type_code)
    scope = RelationScopeGate.objects.select_for_update().get(relation_type=definition, country=country)
    _expect_version(scope, expected_version)
    if not scope.quarantined:
        raise RelationConflict("Scope is already open.")
    scope.quarantined = False
    scope.lock_version += 1
    scope.evidence = evidence
    scope.save(update_fields=["quarantined", "lock_version", "evidence"])
    RelationAuditEvent.objects.create(
        action="reconcile-scope",
        actor=actor,
        base_version=expected_version,
        result={"scope": scope.pk, "evidence": evidence},
    )
    return scope


@transaction.atomic
def set_presentation_selection(*, site, content_locale, entity, anchor, expected_version, actor, approved):
    from .publication_eligibility import lock_publication_graph

    lock_publication_graph()
    if not content_locale or anchor._meta.label_lower not in {"posts.post", "classifier.category"}:
        raise ValidationError("A content locale and catalog anchor are required.")
    anchor = type(anchor).objects.select_for_update().get(pk=anchor.pk)
    if anchor.entity_id != entity.pk:
        raise ValidationError("Anchor must resolve to the selected entity.")
    selection = (
        EntityPresentationSelection.objects.select_for_update()
        .filter(site=site, content_locale=content_locale, entity=entity)
        .first()
    )
    if selection is None:
        if expected_version is not None:
            raise RelationConflict("Presentation selection does not exist.")
        selection = EntityPresentationSelection(site=site, content_locale=content_locale, entity=entity)
    else:
        _expect_version(selection, expected_version)
        selection.lock_version += 1
    selection.post = anchor if anchor._meta.label_lower == "posts.post" else None
    selection.category = anchor if selection.post is None else None
    selection.updated_by = actor
    selection.approved = approved
    selection.save()
    RelationAuditEvent.objects.create(
        selection=selection, action="select-presentation", actor=actor, base_version=expected_version
    )
    return selection
