"""Plant-protection schema validation consumed by the shared relation
writers."""

import json
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.utils import timezone

from .application_models import (
    ApplicationCountryPolicy,
    ApplicationMethod,
    ApplicationReviewerGrant,
    PlantProtectionApplicationDetails,
)
from .models import CatalogEntity
from .validation import validate_database_text

APPLICATION_TYPE = "plant_protection_application"
SOURCE_FIELDS = {
    "reference": "source_reference",
    "document": "source_document",
    "version": "source_version",
    "content_digest": "source_content_digest",
}
IDENTITY_FIELDS = [
    "country",
    "method",
    "formulation_identity",
    "target_locator",
    "registration_authority",
    "registration_record_key",
    "application_locator",
]
PAYLOAD_FIELDS = {field.name for field in PlantProtectionApplicationDetails._meta.fields} - {
    "revision",
    *SOURCE_FIELDS.values(),
}


def source_scope(payload, source, country, digest):
    validate_database_text(payload)
    validate_database_text(source)
    if set(source) != set(SOURCE_FIELDS) or any(
        not isinstance(value, str) or not value.strip() for value in source.values()
    ):
        raise ValidationError("Application source requires reference, document, version and content_digest.")
    if not re.fullmatch(r"[a-f0-9]{64}", source["content_digest"]):
        raise ValidationError("Source content_digest must be a SHA-256 digest.")
    expected_country = payload.get("country")
    if not isinstance(expected_country, str) or not re.fullmatch(r"[A-Z]{2}", expected_country):
        raise ValidationError("Application country must be an explicit two-letter code.")
    if country and country != expected_country:
        raise ValidationError("Application country does not match the revision source scope.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT catalog_identity_digest(%s::jsonb)", [json.dumps(source)])
        canonical = cursor.fetchone()[0]
    if digest and digest != canonical:
        raise ValidationError("Application source version digest does not match its canonical source identity.")
    return expected_country, canonical


def build_details(payload, source, country, participants):
    if set(payload) - (PAYLOAD_FIELDS | {"country"}) or any(key not in payload for key in IDENTITY_FIELDS):
        raise ValidationError(
            "Application payload requires its identity fields and only documented application fields."
        )
    if any(not isinstance(payload[key], str) for key in IDENTITY_FIELDS):
        raise ValidationError("Application identity fields require explicit strings.")
    if payload["country"] != country:
        raise ValidationError("Application country does not match its source scope.")
    if payload.get("formulation_verified") is not None and not isinstance(payload["formulation_verified"], bool):
        raise ValidationError("Formulation verification must be true, false or null.")
    if not isinstance(payload.get("method"), str):
        raise ValidationError("Application method must be a controlled code.")
    method = ApplicationMethod.objects.select_for_update().filter(pk=payload["method"], active=True).first()
    if method is None:
        raise ValidationError("Application method is unavailable.")
    for key in IDENTITY_FIELDS + [
        "target_kind",
        "target_text",
        "regulatory_decision",
        "checked_at",
        "valid_from",
        "valid_until",
    ]:
        value = payload.get(key)
        if value is not None and not isinstance(value, str):
            raise ValidationError("Application text and date fields require strings or explicit null values.")
    data = {key: value for key, value in payload.items() if key not in {"country", "method"}}
    data.update({field: source[key] for key, field in SOURCE_FIELDS.items()})
    details = PlantProtectionApplicationDetails(method=method, **data)
    details.full_clean(exclude=("revision",), validate_unique=False)
    targets = participants.get("target", [])
    if targets:
        if details.target_text == "":
            details.target_text = None
        target = CatalogEntity.objects.get(pk=targets[0])
        if details.target_kind != target.kind or details.target_locator or details.target_text:
            raise ValidationError(
                "An exact target must match its kind and cannot carry unresolved target text or locator."
            )
    elif not details.target_text or not re.fullmatch(r"[a-z0-9][a-z0-9_.:-]{0,127}", details.target_locator):
        raise ValidationError(
            "An unresolved target requires literal source text and an explicit normalized source locator."
        )
    preparation = CatalogEntity.objects.get(pk=participants["preparation"][0])
    if not isinstance(preparation.provenance, dict):
        raise ValidationError("Application preparation provenance must be a structured object.")
    if preparation.provenance.get("formulation_identity") not in (None, details.formulation_identity):
        raise ValidationError("The formulation does not match the preparation identity.")
    canonical = {key: getattr(details, key) for key in PAYLOAD_FIELDS - {"method"}}
    for key in ("checked_at", "valid_from", "valid_until"):
        value = canonical[key]
        canonical[key] = value.isoformat() if value is not None else None
    canonical.update(country=country, method=method.pk)
    return details, canonical


def require_country_reviewer(access, country):
    grant = access._grant(permission="review_relationrecord", write=True, capability="can_review")
    if (
        not access.actor.has_perm("catalog.review_plant_protection_applications")
        or not ApplicationReviewerGrant.objects.select_for_update()
        .filter(site_grant=grant, country_id=country, can_review=True)
        .exists()
    ):
        raise PermissionDenied("Application review requires explicit domain and country authority.")


def require_reviewer(access, revision):
    return require_country_reviewer(access, revision.country)


def require_evidence(revision, *, current):
    details = PlantProtectionApplicationDetails.objects.select_for_update().filter(revision=revision).first()
    policy = ApplicationCountryPolicy.objects.select_for_update().filter(pk=revision.country, active=True).first()
    if details is None or policy is None:
        raise ValidationError("Application evidence or verified country timezone is unavailable.")
    try:
        country_zone = ZoneInfo(policy.timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValidationError("Application country timezone is unavailable.") from exc
    preparation = revision.participants.select_related("entity").get(role="preparation").entity
    if (
        not isinstance(preparation.provenance, dict)
        or preparation.provenance.get("formulation_identity") != details.formulation_identity
    ):
        raise ValidationError("The preparation identity has no matching formulation provenance.")
    if (
        details.formulation_verified is not True
        or not details.formulation_provenance
        or details.regulatory_decision != "confirmed"
        or not details.regulatory_provenance
        or details.checked_at is None
        or details.checked_at > timezone.now()
        or details.valid_from is None
        or details.valid_until is None
        or not ApplicationMethod.objects.select_for_update().filter(pk=details.method_id, active=True).exists()
    ):
        raise ValidationError(
            "Application requires verified formulation, regulatory evidence, check time and known validity bounds."
        )
    withdrawal = revision.record.withdrawals.filter(resulting_epoch=revision.created_epoch).first()
    if withdrawal and details.checked_at < withdrawal.occurred_at:
        raise ValidationError("Application restoration requires a new verification after the withdrawal.")
    if current and not details.valid_from <= timezone.now().astimezone(country_zone).date() <= details.valid_until:
        raise ValidationError("Application is outside its inclusive country-calendar validity interval.")
