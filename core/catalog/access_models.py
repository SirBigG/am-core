from django.conf import settings
from django.db import models
from django.db.models import Q

from .models import CatalogEntity
from .relations import RelationRecord


class RelationSiteGrant(models.Model):
    """Explicit private editorial access to a site."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
    can_edit = models.BooleanField(default=False)
    can_review = models.BooleanField(default=False)
    can_publish = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("actor", "site"), name="catalog_site_actor_grant_unique"),
        ]


class RelationEntityGrant(models.Model):
    """A participant and optional label anchor authorized for a site grant."""

    grant = models.ForeignKey(RelationSiteGrant, on_delete=models.CASCADE)
    entity = models.ForeignKey(CatalogEntity, on_delete=models.PROTECT)
    post = models.ForeignKey("posts.Post", null=True, blank=True, on_delete=models.CASCADE)
    category = models.ForeignKey("classifier.Category", null=True, blank=True, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("grant", "entity"), name="catalog_actor_entity_grant_unique"),
            models.CheckConstraint(
                condition=Q(post__isnull=True) | Q(category__isnull=True),
                name="catalog_grant_at_most_one_anchor",
            ),
        ]


class PrivateRelationSite(models.Model):
    """The site owning editorial access to a private relation and its
    history."""

    record = models.OneToOneField(RelationRecord, primary_key=True, on_delete=models.PROTECT)
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT)
