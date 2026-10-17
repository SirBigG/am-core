"""Shared deletion policy for Guide Hub sections and category deletion
trees."""

from django.core.exceptions import PermissionDenied
from django.db.models import Exists, OuterRef

from core.classifier.models import Category
from core.posts.models import GuideSectionArticle, Post


def require_guide_placement_deletion(admin_site, request, placements):
    if not placements.exists():
        return
    visible_posts = admin_site.get_model_admin(Post).get_queryset(request)
    if placements.exclude(post__in=visible_posts).exists():
        raise PermissionDenied("Guide deletion requires visibility of all referenced articles.")
    # Placements have no standalone ModelAdmin, so Django's deletion collector
    # does not enforce their model permission for us.
    if not request.user.has_perm("posts.delete_guidesectionarticle"):
        raise PermissionDenied("Guide deletion requires placement delete permission.")


def guide_placements_in_category_trees(categories):
    """Include guides below every selected category, using fresh tree
    boundaries."""
    ancestors = Category.objects.filter(
        pk__in=[category.pk for category in categories],
        tree_id=OuterRef("section__category__tree_id"),
        lft__lte=OuterRef("section__category__lft"),
        rght__gte=OuterRef("section__category__rght"),
    )
    return GuideSectionArticle.objects.alias(in_deleted_tree=Exists(ancestors)).filter(in_deleted_tree=True)
