"""Transactional rebuilds and durable, coalesced per-resource refreshes."""

import uuid

from django.contrib.postgres.search import SearchVector
from django.db import connection, transaction
from django.utils import timezone

from .models import ResourceType, SearchDirtyScope, SearchDocument, SearchIndexState
from .sources import local_url, projections

LOCK_ID = 186401818


def write_scope(generation, kind):
    batch = []
    for data in projections(kind):
        if not local_url(data["canonical_url"]):
            continue
        batch.append(SearchDocument(generation=generation, **data))
        if len(batch) == 200:
            SearchDocument.objects.bulk_create(batch)
            batch = []
    if batch:
        SearchDocument.objects.bulk_create(batch)
    SearchDocument.objects.filter(generation=generation, resource_type=kind).update(
        search_vector=(
            SearchVector("normalized_title", config="simple", weight="A")
            + SearchVector("aliases", "taxonomy", config="simple", weight="B")
            + SearchVector("summary", config="simple", weight="C")
            + SearchVector("body", config="simple", weight="D")
        )
    )


@transaction.atomic
def sync_index(*, rebuild=False):
    # Serialize only index workers, not source writers. Read fresh source state;
    # queue revisions created during the build survive compare-and-delete.
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_ID])
    state, _ = SearchIndexState.objects.get_or_create(pk=1)
    rebuild = rebuild or state.active_generation is None
    pending = list(SearchDirtyScope.objects.values_list("pk", "resource_type", "revision")[:100000])
    kinds = list(ResourceType.values) if rebuild else sorted({kind for _, kind, _ in pending})
    if not kinds:
        return 0
    generation = uuid.uuid4() if rebuild else state.active_generation
    for kind in kinds:
        if not rebuild:
            SearchDocument.objects.filter(generation=generation, resource_type=kind).delete()
        write_scope(generation, kind)
    state.active_generation = generation
    state.updated_at = timezone.now()
    state.save(update_fields=["active_generation", "updated_at"])
    # Match the exact snapshot, not a sequence high-water mark: a transaction
    # with an older sequence value may commit after projections were read.
    with connection.cursor() as cursor:
        for offset in range(0, len(pending), 500):
            batch = pending[offset : offset + 500]
            placeholders = ", ".join(["(%s, %s)"] * len(batch))
            cursor.execute(
                "DELETE FROM search_searchdirtyscope AS dirty USING (VALUES "
                + placeholders
                + ") AS processed(id, revision) WHERE dirty.id = processed.id AND dirty.revision = processed.revision",
                [value for pk, _, revision in batch for value in (pk, revision)],
            )
    if rebuild:
        SearchDocument.objects.exclude(generation=generation).delete()
    return len(kinds)
