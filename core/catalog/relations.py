import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from .models import CatalogEntity


class RelationType(models.Model):
    code = models.SlugField(max_length=64, primary_key=True)


class RelationEligibilityFence(models.Model):
    """Database-owned write fence shared by eligibility mutations for one
    type."""

    relation_type = models.OneToOneField(RelationType, primary_key=True, on_delete=models.PROTECT)
    generation = models.PositiveBigIntegerField(default=1)

    class Meta:
        db_table = "catalog_eligibility_fence"
        default_permissions = ()


class RelationTypeVersion(models.Model):
    relation_type = models.ForeignKey(RelationType, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    roles = models.JSONField()
    identity_roles = models.JSONField()
    identity_fields = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("relation_type", "version"), name="catalog_type_version_unique"),
            models.CheckConstraint(condition=Q(version__gte=1), name="catalog_type_version_positive"),
        ]


class RelationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    relation_type = models.ForeignKey(RelationType, on_delete=models.PROTECT)
    identity = models.JSONField(editable=False)
    identity_digest = models.CharField(max_length=64, editable=False)
    lock_version = models.PositiveBigIntegerField(default=1, editable=False)
    archived = models.BooleanField(default=False)
    withdrawn = models.BooleanField(default=False)
    eligibility_epoch = models.PositiveBigIntegerField(default=0, editable=False)
    superseded_by = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        permissions = [
            ("review_relationrecord", "Can review catalog relation revisions"),
            ("publish_relationrecord", "Can release catalog relations on an explicitly granted site"),
            ("review_shared_relations", "Can review relations affecting multiple sites"),
            ("withdraw_relation", "Can globally withdraw relations with explicit domain and site authority"),
            ("reinstate_relation", "Can reinstate relations with new reviewed evidence and explicit authority"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("relation_type", "identity_digest"), name="catalog_record_identity_unique"),
            models.CheckConstraint(condition=Q(lock_version__gte=1), name="catalog_record_version_positive"),
            models.CheckConstraint(
                condition=Q(superseded_by__isnull=True) | Q(withdrawn=True), name="catalog_record_successor_withdrawn"
            ),
        ]


class ReviewState(models.TextChoices):
    DRAFT = "draft", "Draft"
    SUBMITTED = "submitted", "Submitted"
    APPROVED = "approved", "Approved"
    REJECTED = "rejected", "Rejected"


class RelationRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(RelationRecord, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    schema = models.ForeignKey(RelationTypeVersion, on_delete=models.PROTECT)
    payload = models.JSONField(default=dict)
    source = models.JSONField(default=dict)
    country = models.CharField(max_length=2, blank=True)
    source_version_digest = models.CharField(max_length=64, blank=True)
    base_approved_revision = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    sealed = models.BooleanField(default=False, editable=False)
    created_epoch = models.PositiveBigIntegerField(editable=False)
    state = models.CharField(max_length=9, choices=ReviewState, default=ReviewState.DRAFT)
    approval_epoch = models.PositiveBigIntegerField(null=True, editable=False)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    reviewed_at = models.DateTimeField(null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("record", "number"), name="catalog_revision_number_unique"),
            models.CheckConstraint(condition=Q(number__gte=1), name="catalog_revision_number_positive"),
            models.CheckConstraint(
                condition=(
                    Q(
                        state="approved",
                        approval_epoch=models.F("created_epoch"),
                        approval_epoch__isnull=False,
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                    | Q(
                        state="rejected",
                        approval_epoch__isnull=True,
                        reviewed_by__isnull=False,
                        reviewed_at__isnull=False,
                    )
                    | Q(
                        state__in=["draft", "submitted"],
                        approval_epoch__isnull=True,
                        reviewed_by__isnull=True,
                        reviewed_at__isnull=True,
                    )
                ),
                name="catalog_revision_review_coherent",
            ),
        ]
        indexes = [
            models.Index(fields=("record", "state"), name="catalog_record_review_idx"),
            models.Index(fields=("country", "source_version_digest", "record"), name="catalog_revision_source_idx"),
        ]


class RelationParticipant(models.Model):
    revision = models.ForeignKey(RelationRevision, on_delete=models.PROTECT, related_name="participants")
    entity = models.ForeignKey(CatalogEntity, on_delete=models.PROTECT)
    role = models.SlugField(max_length=64)
    ordinal = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("revision", "role", "entity"), name="catalog_participant_unique"),
            models.UniqueConstraint(fields=("revision", "role", "ordinal"), name="catalog_participant_position_unique"),
        ]
        indexes = [models.Index(fields=("entity", "role", "revision"), name="catalog_entity_role_idx")]


class RelationRelease(models.Model):
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    record = models.ForeignKey(RelationRecord, on_delete=models.PROTECT, related_name="releases")
    approved_revision = models.ForeignKey(RelationRevision, on_delete=models.PROTECT)
    enabled = models.BooleanField(default=False)
    lock_version = models.PositiveBigIntegerField(default=1, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("site", "record"), name="catalog_site_release_unique"),
            models.CheckConstraint(condition=Q(lock_version__gte=1), name="catalog_release_version_positive"),
        ]
        indexes = [
            models.Index(fields=("site", "enabled", "record", "approved_revision"), name="catalog_release_lookup_idx")
        ]


class EntityPresentationSelection(models.Model):
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    content_locale = models.CharField(max_length=35)
    entity = models.ForeignKey(CatalogEntity, on_delete=models.PROTECT)
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.PROTECT)
    category = models.ForeignKey("classifier.Category", null=True, blank=True, on_delete=models.PROTECT)
    approved = models.BooleanField(default=False)
    lock_version = models.PositiveBigIntegerField(default=1, editable=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("site", "content_locale", "entity"), name="catalog_selection_unique"),
            models.CheckConstraint(
                condition=Q(post__isnull=True, category__isnull=False) | Q(post__isnull=False, category__isnull=True),
                name="catalog_selection_one_anchor",
            ),
            models.CheckConstraint(condition=Q(lock_version__gte=1), name="catalog_selection_version_positive"),
        ]


class RelationAuditEvent(models.Model):
    record = models.ForeignKey(RelationRecord, null=True, on_delete=models.PROTECT)
    selection = models.ForeignKey(EntityPresentationSelection, null=True, on_delete=models.PROTECT)
    revision = models.ForeignKey(RelationRevision, null=True, on_delete=models.PROTECT)
    action = models.SlugField(max_length=40)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(auto_now_add=True)
    request_id = models.CharField(max_length=128, blank=True)
    base_version = models.PositiveBigIntegerField(null=True)
    source_digest = models.CharField(max_length=64, blank=True)
    result = models.JSONField(default=dict)


class RelationWithdrawal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(RelationRecord, on_delete=models.PROTECT, related_name="withdrawals")
    resulting_epoch = models.PositiveBigIntegerField()
    reason = models.TextField()
    evidence = models.JSONField()
    affected_site_ids = models.JSONField(default=list)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("record", "resulting_epoch"), name="catalog_withdrawal_epoch_unique"),
        ]


class RelationIdentityCorrection(models.Model):
    original = models.OneToOneField(RelationRecord, on_delete=models.PROTECT, related_name="correction")
    successor = models.ForeignKey(RelationRecord, on_delete=models.PROTECT, related_name="+")
    withdrawal = models.OneToOneField(RelationWithdrawal, on_delete=models.PROTECT)
    operation_key = models.CharField(max_length=128)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~Q(original=models.F("successor")), name="catalog_correction_distinct"),
        ]


class SourceWithdrawalGate(models.Model):
    relation_type = models.ForeignKey(RelationType, on_delete=models.PROTECT)
    country = models.CharField(max_length=2)
    source_version_digest = models.CharField(max_length=64)
    evidence = models.JSONField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("relation_type", "country", "source_version_digest"), name="catalog_source_gate_unique"
            ),
        ]


class RelationScopeGate(models.Model):
    relation_type = models.ForeignKey(RelationType, on_delete=models.PROTECT)
    country = models.CharField(max_length=2)
    quarantined = models.BooleanField(default=True)
    source = models.ForeignKey(SourceWithdrawalGate, on_delete=models.PROTECT)
    evidence = models.JSONField(default=dict)
    lock_version = models.PositiveBigIntegerField(default=1, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("relation_type", "country"), name="catalog_scope_gate_unique"),
        ]


class ImportReceipt(models.Model):
    actor_scope = models.CharField(max_length=128)
    operation_key = models.CharField(max_length=128)
    request_digest = models.CharField(max_length=64)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("actor_scope", "operation_key"), name="catalog_import_receipt_unique"),
        ]
