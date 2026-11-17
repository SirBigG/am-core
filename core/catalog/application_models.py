"""Typed evidence for plant-protection application relation revisions."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .access_models import RelationSiteGrant
from .relations import RelationRevision


class ApplicationMethod(models.Model):
    code = models.SlugField(max_length=64, primary_key=True)
    label = models.CharField(max_length=120)
    active = models.BooleanField(default=True)


class ApplicationCountryPolicy(models.Model):
    country = models.CharField(max_length=2, primary_key=True)
    timezone_name = models.CharField(max_length=64)
    active = models.BooleanField(default=False)

    def __str__(self):
        return self.country

    def clean(self):
        try:
            ZoneInfo(self.timezone_name)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise ValidationError({"timezone_name": "A verified IANA timezone is required."}) from exc


class ApplicationReviewerGrant(models.Model):
    site_grant = models.ForeignKey(RelationSiteGrant, on_delete=models.CASCADE)
    country = models.ForeignKey(ApplicationCountryPolicy, on_delete=models.PROTECT)
    can_review = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("site_grant", "country"), name="catalog_application_reviewer_unique")
        ]


class PlantProtectionApplicationDetails(models.Model):
    revision = models.OneToOneField(
        RelationRevision, primary_key=True, on_delete=models.PROTECT, related_name="application"
    )
    formulation_identity = models.CharField(max_length=200)
    formulation_verified = models.BooleanField(null=True, blank=True, default=None)
    formulation_provenance = models.JSONField(default=dict, blank=True)
    method = models.ForeignKey(ApplicationMethod, on_delete=models.PROTECT)
    target_kind = models.CharField(
        max_length=7, choices=[(kind, kind) for kind in ("disease", "pest", "weed", "other")]
    )
    target_locator = models.CharField(max_length=128, blank=True)
    target_text = models.TextField(null=True, blank=True)
    registration_authority = models.CharField(max_length=128)
    registration_record_key = models.CharField(max_length=128)
    application_locator = models.CharField(max_length=128)
    source_reference = models.CharField(max_length=1000)
    source_document = models.CharField(max_length=200)
    source_version = models.CharField(max_length=128)
    source_content_digest = models.CharField(max_length=64)
    checked_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateField(null=True, blank=True)
    valid_until = models.DateField(null=True, blank=True)
    regulatory_decision = models.CharField(
        max_length=10, default="unresolved", choices=[(s, s) for s in ("unresolved", "confirmed", "denied", "expired")]
    )
    regulatory_provenance = models.JSONField(default=dict, blank=True)

    class Meta:
        permissions = [
            (
                "review_plant_protection_applications",
                "Can review plant protection evidence in explicitly granted countries",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_from__isnull=True)
                | Q(valid_until__isnull=True)
                | Q(valid_from__lte=models.F("valid_until")),
                name="catalog_application_dates_ordered",
            ),
            models.CheckConstraint(
                condition=Q(target_kind__in=("disease", "pest", "weed", "other")),
                name="catalog_application_target_kind",
            ),
            models.CheckConstraint(
                condition=Q(regulatory_decision__in=("unresolved", "confirmed", "denied", "expired")),
                name="catalog_application_regulatory_state",
            ),
        ]
        indexes = [
            models.Index(
                fields=("regulatory_decision", "valid_from", "valid_until"), name="catalog_application_dates_idx"
            )
        ]

    def clean(self):
        if self.checked_at and (timezone.is_naive(self.checked_at) or self.checked_at > timezone.now()):
            raise ValidationError({"checked_at": "Use a known timezone and a check time no later than now."})
        if not isinstance(self.formulation_provenance, dict) or not isinstance(self.regulatory_provenance, dict):
            raise ValidationError("Evidence provenance must contain JSON objects.")
