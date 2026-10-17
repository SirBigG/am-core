"""Read-only collection queries; presentation selection belongs to the
caller."""

from django.db.models import Exists, OuterRef, Prefetch

from core.classifier.models import Category, CategoryPresentationMode
from core.posts.models import GuideSection, GuideSectionArticle


def _inactive_category_ancestors(category_path):
    """Include the category itself and every ancestor, at any taxonomy
    depth."""
    prefix = f"{category_path}__" if category_path else ""
    return Category.objects.filter(
        is_active=False,
        tree_id=OuterRef(f"{prefix}tree_id"),
        lft__lte=OuterRef(f"{prefix}lft"),
        rght__gte=OuterRef(f"{prefix}rght"),
    )


def get_public_guide_categories():
    return (
        Category.objects.filter(presentation_mode=CategoryPresentationMode.GUIDE_HUB)
        .alias(has_inactive_category=Exists(_inactive_category_ancestors("")))
        .filter(has_inactive_category=False)
    )


def get_public_guide_sections(category_id):
    """Return sections with ordered eligible placements in ``public_articles``.

    Both sections and placements order by (sort_order, pk). Empty
    sections are omitted. Post status and the complete owning-category
    ancestry govern eligibility; the referenced post need not belong to
    the hub's category. Presentation mode is deliberately not checked,
    allowing future site defaults to be resolved separately. No URL
    generation, writes or caching occur here.
    """
    articles = (
        GuideSectionArticle.objects.filter(post__status=True)
        .alias(has_inactive_category=Exists(_inactive_category_ancestors("post__rubric")))
        .filter(has_inactive_category=False)
        .select_related("post", "post__rubric")
        .order_by("sort_order", "pk")
    )
    sections = (
        GuideSection.objects.filter(category_id=category_id, is_active=True)
        .alias(has_inactive_category=Exists(_inactive_category_ancestors("category")))
        .filter(has_inactive_category=False)
        .select_related("category")
        .order_by("sort_order", "pk")
        .prefetch_related(Prefetch("articles", queryset=articles, to_attr="public_articles"))
    )
    return [section for section in sections if section.public_articles]


def build_guide_hub_context(category, sections):
    """Shared rendering data for public pages and authorized saved-content
    previews."""
    posts = {article.post_id: article.post for section in sections for article in section.public_articles}
    return {
        "category": category,
        "guide_sections": sections,
        "guide_menu_items": Category.objects.filter(parent_id=category.parent_id, is_active=True).values(
            "slug", "value", "absolute_url"
        ),
        "post_count": len(posts),
        # Dictionaries prevent metadata helpers from generating/saving absent URLs.
        "object_list": [
            {"title": post.title, "absolute_url": post.absolute_url} for post in posts.values() if post.absolute_url
        ],
    }
