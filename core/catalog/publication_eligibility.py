"""Fresh, explicitly scoped eligibility for relation publication
participants."""

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from core.classifier.models import Category
from core.classifier.publication_checks import SiteCategoryConfiguration, SiteContentPolicy
from core.posts.models import Post
from core.posts.publication_checks import PostPublicationApproval, SitePostPublication, material_digest

from .models import CatalogEntity, CatalogEntityState
from .relations import EntityPresentationSelection


def lock_publication_graph():
    """Serialize the small editorial graph before taking its anchor locks."""
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Publication graph lock requires an atomic transaction.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtextextended('catalog-publication-graph-v1', 0))")


class PublicationUnavailable(ValidationError):
    def __init__(self):
        super().__init__("An approved publication is unavailable for this site and content language.")


def _canonical(path):
    return (
        isinstance(path, str)
        and path.startswith("/")
        and not path.startswith("//")
        and "?" not in path
        and "#" not in path
        and "\\" not in path
    )


def _policy(site_id, locale, lock):
    qs = SiteContentPolicy.objects
    if lock:
        qs = qs.select_for_update()
    policy = qs.filter(site_id=site_id, active=True).first()
    if (
        not policy
        or not isinstance(locale, str)
        or not locale
        or not isinstance(policy.content_locales, list)
        or locale not in policy.content_locales
    ):
        raise PublicationUnavailable
    return policy


def _category(category_id, site_id, locale, lock):
    query = Category.objects
    if lock:
        list(query.select_for_update().order_by("pk").values_list("pk", flat=True))
    category = query.filter(pk=category_id).first()
    if category is None:
        raise PublicationUnavailable
    ancestors = list(
        query.order_by("pk").filter(
            tree_id=category.tree_id,
            lft__lte=category.lft,
            rght__gte=category.rght,
        )
    )
    if not ancestors or any(not item.is_active for item in ancestors):
        raise PublicationUnavailable
    configs = SiteCategoryConfiguration.objects.filter(
        site_id=site_id, content_locale=locale, category_id__in=[item.pk for item in ancestors]
    ).order_by("pk")
    if lock:
        configs = configs.select_for_update()
    configs = {row.category_id: row for row in configs}
    # The invisible root has no page, but all category nodes require a scoped
    # configuration; this avoids treating an absent membership as global access.
    for ancestor in ancestors:
        config = configs.get(ancestor.pk)
        if not config or not config.visible or not _canonical(config.canonical_path):
            raise PublicationUnavailable
    return configs[category.pk].canonical_path


def _post(post_id, site_id, locale, policy, lock, now):
    posts = Post.objects
    if lock:
        posts = posts.select_for_update()
    post = posts.filter(pk=post_id, status=True, publish_date__lte=now).first()
    if not post:
        raise PublicationUnavailable
    publications = SitePostPublication.objects.filter(
        post=post, site_id=site_id, content_locale=locale, enabled=True, publish_at__lte=now
    )
    if lock:
        publications = publications.select_for_update()
    publication = publications.first()
    if not publication or publication.category_id != post.rubric_id:
        raise PublicationUnavailable
    approvals = PostPublicationApproval.objects
    if lock:
        approvals = approvals.select_for_update()
    approval = approvals.filter(
        pk=publication.approval_id, post=post, content_locale=locale, reviewed_at__lte=now
    ).first()
    if not approval or approval.content_digest != material_digest(post) or not approval.provenance:
        raise PublicationUnavailable
    if locale == "und":
        if (
            not policy.allow_legacy_und
            or not approval.legacy_published
            or approval.language_verified
            or approval.legacy_site_id != site_id
        ):
            raise PublicationUnavailable
    elif not approval.language_verified:
        raise PublicationUnavailable
    if not _canonical(publication.canonical_path) or publication.canonical_path != post.absolute_url:
        raise PublicationUnavailable
    _category(post.rubric_id, site_id, locale, lock)
    return post.entity_id, publication.canonical_path


def eligible_participant_urls(*, site_id, content_locale, entity_ids, lock=False):
    """Resolve every participant or fail the operation without a partial
    result."""
    if lock and not transaction.get_connection().in_atomic_block:
        raise RuntimeError("Locked eligibility requires an atomic transaction.")
    if lock:
        lock_publication_graph()
    policy = _policy(site_id, content_locale, lock)
    ids = set(entity_ids)
    query = EntityPresentationSelection.objects.filter(
        site_id=site_id, content_locale=content_locale, entity_id__in=ids, approved=True
    ).order_by("entity_id")
    initial = {row.entity_id: row for row in query}
    if set(initial) != ids:
        raise PublicationUnavailable
    if lock:
        # Match the existing selection writer: anchors precede selections.
        # Re-read the selections after locking anchors and reject a changed
        # binding instead of acquiring more anchor locks in reverse order.
        post_ids = {selection.post_id for selection in initial.values() if selection.post_id}
        list(Post.objects.select_for_update().filter(pk__in=post_ids).order_by("pk").values_list("pk", flat=True))
        list(Category.objects.select_for_update().order_by("pk").values_list("pk", flat=True))
        selections = {row.entity_id: row for row in query.select_for_update()}
        if set(selections) != ids or any(
            (row.post_id, row.category_id) != (initial[key].post_id, initial[key].category_id)
            for key, row in selections.items()
        ):
            raise PublicationUnavailable
    else:
        selections = initial
    entities = CatalogEntity.objects.filter(pk__in=ids, state=CatalogEntityState.ACTIVE).order_by("pk")
    if lock:
        entities = entities.select_for_update()
    entities = {row.pk: row for row in entities}
    if set(entities) != ids:
        raise PublicationUnavailable
    urls = {}
    for entity_id in sorted(ids):
        selection = selections[entity_id]
        if selection.post_id:
            mapped_entity, url = _post(selection.post_id, site_id, content_locale, policy, lock, timezone.now())
            if mapped_entity != entity_id:
                raise PublicationUnavailable
        elif selection.category_id and entities[entity_id].kind == "crop":
            category = Category.objects.filter(pk=selection.category_id, entity_id=entity_id).first()
            if not category:
                raise PublicationUnavailable
            url = _category(category.pk, site_id, content_locale, lock)
        else:
            raise PublicationUnavailable
        urls[entity_id] = url
    return urls
