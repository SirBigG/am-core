import uuid

from django.conf import settings
from django.db import models


class CatalogEntityKind(models.TextChoices):
    CROP = "crop", "Crop"
    CULTIVAR = "cultivar", "Cultivar"
    DISEASE = "disease", "Disease"
    PEST = "pest", "Pest"
    WEED = "weed", "Weed"
    PREPARATION = "preparation", "Preparation"


class CatalogEntityState(models.TextChoices):
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class CatalogEntity(models.Model):
    """Stable identity shared by catalog materials and relation
    participants."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=CatalogEntityKind)
    state = models.CharField(max_length=8, choices=CatalogEntityState, default=CatalogEntityState.ACTIVE)
    provenance = models.JSONField()
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveBigIntegerField(default=1, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(kind__in=CatalogEntityKind.values), name="catalog_entity_kind"),
            models.CheckConstraint(
                condition=models.Q(state__in=CatalogEntityState.values), name="catalog_entity_state"
            ),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="catalog_entity_positive_version"),
        ]
