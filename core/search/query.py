from django.contrib.postgres.search import SearchQuery, SearchRank, TrigramSimilarity
from django.db.models import Case, Count, F, FloatField, IntegerField, Q, Value, When

from .inputs import MAX_QUERY_LENGTH
from .models import SearchDocument, SearchIndexState
from .sources import normalize, visible_documents


def search_documents(query, *, archive=False):
    query = normalize(query)[:MAX_QUERY_LENGTH]
    generation = SearchIndexState.objects.filter(pk=1).values("active_generation")[:1]
    documents = visible_documents(SearchDocument.objects.filter(generation=generation), archive=archive)
    if not query:
        return documents.none()
    tsquery = SearchQuery(query, config="simple", search_type="plain")
    candidates = Q(search_vector=tsquery) | Q(normalized_title=query)
    # Both operators have GIN paths. No unbounded icontains scan on bodies.
    if len(query) >= 3:
        candidates |= Q(normalized_title__trigram_similar=query) | Q(normalized_title__contains=query)
    return (
        documents.filter(candidates)
        .annotate(
            relevance_tier=Case(
                When(normalized_title=query, then=Value(3)),
                When(normalized_title__contains=query, then=Value(2)),
                When(search_vector=tsquery, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            ),
            score=SearchRank(F("search_vector"), tsquery, normalization=32)
            + (
                TrigramSimilarity("normalized_title", query)
                if len(query) >= 3
                else Value(0.0, output_field=FloatField())
            ),
        )
        .order_by("-relevance_tier", "-score", "resource_type", "source_id")
    )


def result_counts(queryset):
    return dict(
        queryset.order_by().values("resource_type").annotate(total=Count("pk")).values_list("resource_type", "total")
    )
