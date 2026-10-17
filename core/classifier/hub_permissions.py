"""Shared permission checks for deletion of hub configuration references."""

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef, Q

from core.classifier.models import Category, CategoryHubSection


def require_hub_section_deletion(request, sections):
    # Hub sections have no standalone ModelAdmin. Django's deletion collector
    # therefore does not enforce their model permission on parent cascades.
    if not request.user.has_perm("classifier.delete_categoryhubsection") and sections.exists():
        raise PermissionDenied("Deleting hub sections requires hub-section delete permission.")


def hub_sections_in_category_trees(categories):
    """Include owned sections AND references targeting a deleted category.

    A cross-branch target's deletion cascades to the reference even when
    its owning hub is outside the selected taxonomy subtree.
    """
    ids = [category.pk for category in categories]

    def deleted_ancestors(path):
        return Category.objects.filter(
            pk__in=ids,
            tree_id=OuterRef(f"{path}__tree_id"),
            lft__lte=OuterRef(f"{path}__lft"),
            rght__gte=OuterRef(f"{path}__rght"),
        )

    return CategoryHubSection.objects.alias(
        deleted_owner=Exists(deleted_ancestors("hub__category")),
        deleted_target=Exists(deleted_ancestors("category")),
    ).filter(Q(deleted_owner=True) | Q(deleted_target=True))
