from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class ResourceType(models.TextChoices):
    POST = "post", "Матеріали"
    CATEGORY = "category", "Категорії"
    ADVERT = "advert", "Оголошення"
    MARKET = "market", "Агромаркет"
    COMPANY = "company", "Компанії"
    EVENT = "event", "Події"


class SearchDocument(models.Model):
    generation = models.UUIDField()
    resource_type = models.CharField(max_length=16, choices=ResourceType)
    source_id = models.PositiveBigIntegerField()
    canonical_url = models.CharField(max_length=1500)
    title = models.CharField(max_length=512)
    normalized_title = models.CharField(max_length=512)
    summary = models.TextField(blank=True)
    body = models.TextField(blank=True)
    aliases = models.TextField(blank=True)
    taxonomy = models.TextField(blank=True)
    search_vector = SearchVectorField(null=True)
    indexed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["generation", "resource_type", "source_id"], name="search_document_identity"
            ),
        ]
        indexes = [
            GinIndex(fields=["search_vector"], name="search_document_fts"),
            GinIndex(fields=["normalized_title"], opclasses=["gin_trgm_ops"], name="search_document_title_trgm"),
        ]


class SearchIndexState(models.Model):
    # One active generation. Readers see the old or new complete index.
    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    active_generation = models.UUIDField(null=True)
    updated_at = models.DateTimeField(auto_now=True)


class SearchDirtyScope(models.Model):
    """Coalesced durable invalidation; PostgreSQL triggers cover bulk SQL
    too."""

    resource_type = models.CharField(max_length=16, choices=ResourceType)
    transaction_id = models.BigIntegerField()
    revision = models.BigIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["resource_type", "transaction_id"], name="search_dirty_transaction_scope")
        ]
