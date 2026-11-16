"""Explicit authorization for private catalog relation discovery and
editing."""

from dataclasses import dataclass
from uuid import UUID

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Q
from django.http import Http404

from core.classifier.models import Category
from core.posts.models import Post

from . import relation_service
from .access_models import PrivateRelationSite, RelationEntityGrant, RelationSiteGrant
from .applications import APPLICATION_TYPE, require_evidence, require_reviewer
from .models import CatalogEntityState
from .publication_eligibility import eligible_participant_urls, lock_publication_graph
from .relations import RelationParticipant, RelationRecord, RelationRevision, RelationType
from .validation import validate_database_text


def configured_relation_site():
    """Use the server's configured site, never a form field or Host header."""
    return getattr(settings, "SITE_ID", None)


@dataclass(frozen=True)
class RelationAccess:
    actor: object
    site_id: int | None

    def _grant(self, *, permission="view_relationrecord", write=False, capability="can_edit"):
        if (
            not self.site_id
            or not self.actor.is_authenticated
            or not self.actor.is_active
            or not self.actor.is_staff
            or not self.actor.has_perm("catalog.view_relationrecord")
            or not self.actor.has_perm(f"catalog.{permission}")
        ):
            raise PermissionDenied("Catalog relation access is unavailable.")
        qs = RelationSiteGrant.objects.filter(actor=self.actor, site_id=self.site_id)
        if write:
            lock_publication_graph()
            qs = qs.select_for_update().filter(**{capability: True})
        grant = qs.first()
        if grant is None:
            raise PermissionDenied("Catalog relation access is unavailable.")
        return grant

    def _participants(self, grant):
        return RelationEntityGrant.objects.filter(grant=grant).filter(
            Q(post__isnull=True, category__isnull=True)
            | Q(post__entity_id=F("entity_id"))
            | Q(category__entity_id=F("entity_id"))
        )

    def participants(self):
        return self._participants(self._grant()).filter(entity__state=CatalogEntityState.ACTIVE)

    def records(self):
        return self._records(self._grant())

    def _records(self, grant):
        outside_scope = RelationParticipant.objects.filter(revision__record_id=OuterRef("pk")).exclude(
            entity_id__in=self._participants(grant).values("entity_id")
        )
        return RelationRecord.objects.filter(privaterelationsite__site_id=grant.site_id).filter(~Exists(outside_scope))

    def _require_participants(self, grant, participants):
        try:
            requested = {UUID(str(item)) for ids in participants.values() for item in ids}
        except (AttributeError, TypeError, ValueError) as exc:
            raise ValidationError("Participants must contain entity UUIDs.") from exc
        available = set(
            self._participants(grant)
            .filter(entity_id__in=requested, entity__state=CatalogEntityState.ACTIVE)
            .values_list("entity_id", flat=True)
        )
        if requested != available:
            raise ValidationError("A selected participant is unavailable.", code="participant_unavailable")

    def _lock_participant_scope(self, grant):
        # Lock grant rows before Post and Category anchors, each in PK order.
        # The subsequent scope query must see the current mapping and keep it
        # valid through the trusted mutation.
        anchors = list(
            RelationEntityGrant.objects.select_for_update()
            .filter(grant=grant)
            .order_by("pk")
            .values_list("post_id", "category_id")
        )
        for model, index in ((Post, 0), (Category, 1)):
            ids = {row[index] for row in anchors if row[index] is not None}
            list(model.objects.select_for_update().filter(pk__in=ids).order_by("pk").values_list("pk", flat=True))

    def _require_record(self, grant, record_id):
        self._lock_participant_scope(grant)
        binding = PrivateRelationSite.objects.select_for_update().filter(record_id=record_id, site_id=grant.site_id)
        if not binding.exists() or not self._records(grant).filter(pk=record_id).exists():
            raise Http404("Catalog relation is unavailable.")

    @transaction.atomic
    def save_draft(
        self,
        *,
        type_code,
        schema_version,
        participants,
        payload=None,
        source=None,
        country="",
        source_version_digest="",
        record_id=None,
        expected_version=None,
    ):
        permission = "add_relationrecord" if record_id is None else "change_relationrecord"
        grant = self._grant(permission=permission, write=True)
        if record_id is None:
            self._lock_participant_scope(grant)
        else:
            self._require_record(grant, record_id)
        self._require_participants(grant, participants)
        try:
            revision = relation_service.save_draft(
                type_code=type_code,
                schema_version=schema_version,
                participants=participants,
                actor=self.actor,
                payload=payload,
                source=source,
                country=country,
                source_version_digest=source_version_digest,
                record_id=record_id,
                expected_version=expected_version,
            )
        except relation_service.RelationConflict as exc:
            if exc.code == "duplicate_relation":
                # A global identity collision must not disclose another site's record.
                raise ValidationError(
                    "This relation cannot be created with the supplied participants.", code="duplicate_relation"
                ) from exc
            raise
        if record_id is None:
            PrivateRelationSite.objects.create(record_id=revision.record_id, site_id=grant.site_id)
        return revision

    @transaction.atomic
    def submit(self, *, record_id, revision_id, expected_version, validate_only=False):
        grant = self._grant(permission="change_relationrecord", write=True)
        self._require_record(grant, record_id)
        try:
            return relation_service.review_revision(
                record_id=record_id,
                revision_id=revision_id,
                expected_version=expected_version,
                action="submit",
                actor=self.actor,
                validate_only=validate_only,
            )
        except relation_service.RelationRevision.DoesNotExist as exc:
            raise Http404("Catalog revision is unavailable.") from exc

    @transaction.atomic
    def archive_private(self, *, record_id, expected_version):
        grant = self._grant(permission="change_relationrecord", write=True)
        self._require_record(grant, record_id)
        relation_service.archive_record(
            record_id=record_id,
            expected_version=expected_version,
            actor=self.actor,
            private_only=True,
        )

    def _publication_record(self, grant, record_id):
        self._require_record(grant, record_id)
        type_code = RelationRecord.objects.values_list("relation_type_id", flat=True).get(pk=record_id)
        RelationType.objects.select_for_update().get(pk=type_code)
        record = RelationRecord.objects.select_for_update().get(pk=record_id)
        # Only delivered generic and application schemas have an editorial review adapter.
        if type_code not in {"related_to", "cultivar_of", APPLICATION_TYPE}:
            raise PermissionDenied("A domain review adapter is required for this relation type.")
        return record

    def _eligible_revision(self, record, revision_id, content_locale):
        try:
            revision = record.revisions.get(pk=revision_id)
        except RelationRevision.DoesNotExist as exc:
            raise Http404("Catalog revision is unavailable.") from exc
        entity_ids = set(revision.participants.values_list("entity_id", flat=True))
        eligible_participant_urls(
            site_id=self.site_id,
            content_locale=content_locale,
            entity_ids=entity_ids,
            lock=True,
        )
        return revision

    @transaction.atomic
    def review(self, *, record_id, revision_id, expected_version, content_locale, approve, validate_only=False):
        grant = self._grant(permission="review_relationrecord", write=True, capability="can_review")
        record = self._publication_record(grant, record_id)
        if approve:
            revision = self._eligible_revision(record, revision_id, content_locale)
        else:
            try:
                revision = record.revisions.get(pk=revision_id)
            except RelationRevision.DoesNotExist as exc:
                raise Http404("Catalog revision is unavailable.") from exc
        if record.relation_type_id == APPLICATION_TYPE:
            require_reviewer(self, revision)
            if approve:
                require_evidence(revision, current=False)
        sites = set(record.releases.filter(enabled=True).values_list("site_id", flat=True)) | {self.site_id}
        if approve and len(sites) > 1:
            if not self.actor.has_perm("catalog.review_shared_relations"):
                raise PermissionDenied("Shared review requires the platform capability.")
            for site_id in sorted(sites - {self.site_id}):
                other = RelationAccess(self.actor, site_id)
                other_grant = other._grant(permission="review_relationrecord", write=True, capability="can_review")
                if record.relation_type_id == APPLICATION_TYPE:
                    require_reviewer(other, revision)
                other._lock_participant_scope(other_grant)
                other._require_participants(
                    other_grant, {"member": list(revision.participants.values_list("entity_id", flat=True))}
                )
                eligible_participant_urls(
                    site_id=site_id,
                    content_locale=content_locale,
                    entity_ids=list(revision.participants.values_list("entity_id", flat=True)),
                    lock=True,
                )
        return relation_service.review_revision(
            record_id=record.pk,
            revision_id=revision.pk,
            expected_version=expected_version,
            action="approve" if approve else "reject",
            actor=self.actor,
            validate_only=validate_only,
        )

    @transaction.atomic
    def release(self, *, record_id, revision_id, expected_version, content_locale, enabled, validate_only=False):
        grant = self._grant(permission="publish_relationrecord", write=True, capability="can_publish")
        record = self._publication_record(grant, record_id)
        if enabled:
            revision = self._eligible_revision(record, revision_id, content_locale)
            if record.relation_type_id == APPLICATION_TYPE:
                require_evidence(revision, current=True)
            if revision.state != "approved":
                raise relation_service.RelationConflict("Only an approved revision can be published.")
        else:
            try:
                revision = record.revisions.get(pk=revision_id)
            except RelationRevision.DoesNotExist as exc:
                raise Http404("Catalog revision is unavailable.") from exc
        return relation_service.set_release(
            record_id=record.pk,
            revision_id=revision.pk,
            expected_version=expected_version,
            site=grant.site,
            actor=self.actor,
            enabled=enabled,
            validate_only=validate_only,
        )

    @transaction.atomic
    def archive(self, *, record_id, expected_version, validate_only=False):
        grant = self._grant(permission="change_relationrecord", write=True)
        record = self._publication_record(grant, record_id)
        sites = set(record.releases.values_list("site_id", flat=True))
        for site_id in sorted(sites):
            publisher = RelationAccess(self.actor, site_id)
            publisher._grant(permission="publish_relationrecord", write=True, capability="can_publish")
        return relation_service.archive_record(
            record_id=record.pk,
            expected_version=expected_version,
            actor=self.actor,
            validate_only=validate_only,
        )

    def _application_global_authority(self, *, record_id, permission):
        grant = self._grant(permission=permission, write=True, capability="can_review")
        record = self._publication_record(grant, record_id)
        if record.relation_type_id != APPLICATION_TYPE:
            raise PermissionDenied("This action requires an application domain adapter.")
        revision = record.revisions.order_by("-number").first()
        if revision is None:
            raise ValidationError("Application revision is unavailable.")
        require_reviewer(self, revision)
        sites = set(record.releases.values_list("site_id", flat=True)) | {self.site_id}
        if len(sites) > 1 and not self.actor.has_perm("catalog.review_shared_relations"):
            raise PermissionDenied("A global multi-site action requires the platform capability.")
        entities = set(record.revisions.values_list("participants__entity_id", flat=True))
        for site_id in sorted(sites):
            other = RelationAccess(self.actor, site_id)
            publisher = other._grant(permission="publish_relationrecord", write=True, capability="can_publish")
            require_reviewer(other, revision)
            other._lock_participant_scope(publisher)
            if entities - set(other._participants(publisher).values_list("entity_id", flat=True)):
                raise PermissionDenied("Global application actions require all historical participant grants.")
        return record

    @transaction.atomic
    def withdraw_application(self, *, record_id, expected_version, reason, evidence, operation_key):
        self._application_global_authority(record_id=record_id, permission="withdraw_relation")
        if not isinstance(evidence, dict) or not evidence or not isinstance(reason, str) or not reason.strip():
            raise ValidationError("Withdrawal requires an explicit reason and structured evidence.")
        validate_database_text(evidence)
        validate_database_text(reason)
        return relation_service.withdraw_record(
            record_id=record_id,
            expected_version=expected_version,
            actor=self.actor,
            reason=reason,
            evidence=evidence,
            operation_key=operation_key,
        )

    @transaction.atomic
    def reinstate_application(self, *, record_id, revision_id, withdrawal_id, expected_version, evidence):
        record = self._application_global_authority(record_id=record_id, permission="reinstate_relation")
        if not isinstance(evidence, dict) or not evidence:
            raise ValidationError("Reinstatement requires structured evidence resolving the withdrawal.")
        validate_database_text(evidence)
        try:
            revision = record.revisions.get(pk=revision_id)
        except RelationRevision.DoesNotExist as exc:
            raise Http404("Application revision is unavailable.") from exc
        if revision.state != "approved":
            raise relation_service.RelationConflict(
                "Reinstatement requires an approved revision.", code="invalid_transition"
            )
        require_evidence(revision, current=True)
        return relation_service.reinstate_record(
            record_id=record.pk,
            revision_id=revision.pk,
            withdrawal_id=withdrawal_id,
            expected_version=expected_version,
            actor=self.actor,
            evidence=evidence,
        )
