import hashlib
import time

from django.core.cache import cache
from django.db.models import Case, Count, IntegerField, Max, Min, When

DEFAULT_ROTATION_SECONDS = 3600


def rotation_bucket(seconds=DEFAULT_ROTATION_SECONDS):
    return int(time.time() // seconds)


def get_rotating_ids(queryset, scope, limit, seconds=DEFAULT_ROTATION_SECONDS):
    model_label = queryset.model._meta.label_lower
    bucket = rotation_bucket(seconds)
    signature = queryset.aggregate(total=Count("pk"), first_id=Min("pk"), last_id=Max("pk"))
    total = signature["total"]
    cache_key = (
        f"rotating_ids_v2:{model_label}:{scope}:{limit}:{bucket}:"
        f"{total}:{signature['first_id']}:{signature['last_id']}"
    )
    ids = cache.get(cache_key)
    if ids is not None:
        return ids

    ordered = queryset.order_by("pk")
    if total <= limit:
        ids = list(ordered.values_list("pk", flat=True))
    else:
        digest = hashlib.sha256(f"{model_label}:{scope}:{bucket}".encode()).digest()
        offset = int.from_bytes(digest[:8], "big") % (total - limit + 1)
        ids = list(ordered.values_list("pk", flat=True)[offset : offset + limit])
    cache.set(cache_key, ids, seconds + 60)
    return ids


def order_by_id_list(queryset, ids):
    if not ids:
        return queryset.none()
    ordering = Case(
        *(When(pk=pk, then=position) for position, pk in enumerate(ids)),
        output_field=IntegerField(),
    )
    return queryset.filter(pk__in=ids).order_by(ordering)
