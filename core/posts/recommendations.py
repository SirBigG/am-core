import random

from django.core.cache import cache

from core.posts.models import Post
from core.utils.rotating import order_by_id_list

RANDOM_RECOMMENDATION_CANDIDATES_CACHE_KEY = "random_recommendation_candidates_v1"
RANDOM_RECOMMENDATION_CANDIDATES_CACHE_TTL = 300


def _candidate_pool():
    candidates = cache.get(RANDOM_RECOMMENDATION_CANDIDATES_CACHE_KEY)
    if candidates is None:
        candidates = list(
            Post.objects.filter(status=True, photo__image__isnull=False)
            .exclude(photo__image="")
            .order_by()
            .values_list("pk", "rubric__tree_id")
            .distinct()
        )
        cache.set(
            RANDOM_RECOMMENDATION_CANDIDATES_CACHE_KEY,
            candidates,
            RANDOM_RECOMMENDATION_CANDIDATES_CACHE_TTL,
        )
    return candidates


def _diverse_ids(candidates, limit, rng):
    shuffled = list(candidates)
    rng.shuffle(shuffled)

    selected_ids = []
    selected_id_set = set()
    selected_trees = set()
    for post_id, tree_id in shuffled:
        if tree_id in selected_trees:
            continue
        selected_ids.append(post_id)
        selected_id_set.add(post_id)
        selected_trees.add(tree_id)
        if len(selected_ids) == limit:
            return selected_ids

    for post_id, _tree_id in shuffled:
        if post_id in selected_id_set:
            continue
        selected_ids.append(post_id)
        selected_id_set.add(post_id)
        if len(selected_ids) == limit:
            break
    return selected_ids


def get_random_recommendations(*, current_post_id=None, exclude_ids=(), limit=4, rng=None):
    rng = rng or random.SystemRandom()
    hard_exclusions = {current_post_id} if current_post_id else set()
    refresh_exclusions = {post_id for post_id in exclude_ids if post_id}
    candidates = _candidate_pool()

    preferred_candidates = [
        candidate
        for candidate in candidates
        if candidate[0] not in hard_exclusions and candidate[0] not in refresh_exclusions
    ]
    selected_ids = _diverse_ids(preferred_candidates, limit, rng)

    if len(selected_ids) < limit:
        fallback_candidates = [
            candidate
            for candidate in candidates
            if candidate[0] not in hard_exclusions and candidate[0] not in selected_ids
        ]
        fallback_ids = _diverse_ids(fallback_candidates, limit - len(selected_ids), rng)
        selected_ids.extend(fallback_ids)

    posts = order_by_id_list(Post.objects.select_objects(), selected_ids)
    return list(posts)
