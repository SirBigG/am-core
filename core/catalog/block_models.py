"""Scoped, versioned query configuration, separate from relation evidence."""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class BlockConfiguration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hub = models.ForeignKey("classifier.CategoryHub", on_delete=models.PROTECT, related_name="catalog_configurations")
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    content_locale = models.CharField(max_length=35)
    owner = models.ForeignKey("catalog.CatalogEntity", on_delete=models.PROTECT)
    lock_version = models.PositiveBigIntegerField(default=1, editable=False)
    enabled = models.BooleanField(default=False)
    active_revision = models.ForeignKey(
        "BlockConfigurationRevision", null=True, on_delete=models.PROTECT, related_name="+"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("hub", "site", "content_locale"), name="catalog_block_scope_unique"),
            models.CheckConstraint(condition=Q(lock_version__gte=1), name="catalog_block_version_positive"),
            models.CheckConstraint(
                condition=Q(enabled=False) | Q(active_revision__isnull=False), name="catalog_block_enabled_revision"
            ),
        ]
        permissions = [("publish_blockconfiguration", "Can activate explicitly scoped catalog block configuration")]


class BlockConfigurationRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    configuration = models.ForeignKey(BlockConfiguration, on_delete=models.PROTECT, related_name="revisions")
    number = models.PositiveIntegerField()
    blocks = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("configuration", "number"), name="catalog_block_revision_unique")
        ]


class BlockManualPlacement(models.Model):
    revision = models.ForeignKey(BlockConfigurationRevision, on_delete=models.PROTECT, related_name="manual_bindings")
    slot = models.CharField(max_length=64)
    placement = models.ForeignKey("posts.GuideSectionArticle", on_delete=models.PROTECT)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("revision", "placement"), name="catalog_block_manual_unique")]


class BlockConfigurationAudit(models.Model):
    configuration = models.ForeignKey(BlockConfiguration, on_delete=models.PROTECT, related_name="audit_events")
    revision = models.ForeignKey(BlockConfigurationRevision, null=True, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=16)
    base_version = models.PositiveBigIntegerField()
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
