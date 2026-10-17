# Guide Hub data foundation

Deployment, access assignments and rollback: [Guide Hub rollout](guide-hub-rollout.md).

Editorial workflow: [Managing category pages and widgets](../business/guides/category-pages-and-widgets.md).
The later [hub management API](api/hub-management.md) extends this foundation
with authenticated section/placement CRUD and presentation management.

Guide Hub is a curated collection of references to existing `posts.Post` rows.
Its data lives in `core.posts`; the shared taxonomy remains in `core.classifier`.

## Current contract

- `Category.presentation_mode` defaults to `catalog`; `guide_hub` selects the
  curated guide on the existing two-segment category route.
- `GuideSection.category` identifies its owning category by foreign key.
  Sections have a title, optional plain-text description, `sort_order` and
  `is_active`. Empty sections and repeated titles are allowed.
- `GuideSectionArticle` references a section and an existing post, with a
  database unique constraint on `(section, post)`.
- Both sections and placements order by `(sort_order, pk)`. Equal positions
  are allowed. Positions use nonnegative integers, following attribute-schema
  conventions.
- Posts can be referenced from several sections and from other categories.
  Placements do not save or reclassify their posts, and do not change content,
  publication status, slugs or stored canonical URLs.
- Deleting a section cascades to its placements, never its posts. Deleting a
  referenced post removes its placements, never its sections. Deleting a hub
  cascades to its sections; the existing `Post.rubric` deletion rules remain
  unchanged for articles actually owned by that category.
- No enforcement requires sections to belong to a category currently set to
  `guide_hub`; this allows preparation and later presentation changes without
  deleting curation.

The foundation introduced no new public article routes. Existing article-detail
behavior stays in place. Agent configuration endpoints were added later; see
the API reference linked above.

## Django Admin management

Category forms expose the presentation default and a GuideSection inline with
title, description, visibility and numeric `sort_order`. Saved sections have a
change link to their own section admin page. The inline remains available for
catalog categories so editors can prepare a guide before switching its mode.

The GuideSection admin supports category autocomplete, title/category search,
visibility/presentation filters, and an ordered article-placement inline.
Editors select existing posts with the built-in Django Admin autocomplete,
which reuses `PostAdmin` title/text search and its request-scoped queryset.
Placements are edited and deleted here; there is no standalone placement Admin,
nested inline package or drag-and-drop dependency. Agents can also manage
placements through the later content API.

Sections and placements use their existing standard Django add/view/change/delete
model permissions. Category permission or `change_own_post` alone does not grant
curation rights. Grant GuideSection and GuideSectionArticle permissions separately
through the existing user/group admin; this feature makes no automatic grants.
Section permissions are global curation rights, not per-publisher ownership.

Article selection also requires the existing article visibility permissions:
global `view_post`/`change_post` users can select all posts, while
`change_own_post` users see only their own posts. The same PostAdmin queryset
restricts inline rows and submitted FK choices, preventing forged post IDs from
bypassing autocomplete. Editing visible placements leaves hidden placements
intact. Without article visibility, autocomplete is denied and assignment choices
are empty. Inactive articles remain selectable for editorial preparation;
the public collection eligibility rules still exclude them.

Deleting a section with placements requires placement-delete permission as well
as section-delete permission. The category inline conservatively hides its
deletion controls without both. Every
section deletion path rechecks all affected placements against PostAdmin article
visibility, including forged inline submissions. A denied inline deletion rolls
back the category form transaction.

Individual and bulk section/category deletion confirmations return 403 when their
related-object tree would disclose an article outside the editor's PostAdmin
visibility or when placement-delete permission is missing. Category checks cover
the entire selected subtree. Confirmed MPTT bulk deletion repeats the related
permission preflight on POST, including when a confirmation is forged or stale;
mixed selections are checked before any category is deleted.

Full section history requires existing global `view_post` or `change_post`
permission in addition to the normal section permission. Own-article scope is
insufficient because historical placement labels may contain another author's
title even after a placement was removed or an article was reassigned. Audit
entries remain intact; unauthorized history requests return 403.

Duplicate section/post assignments produce normal formset validation errors.
Equal numeric positions are allowed and use primary-key ordering to break ties.
Admin placement changes do not save articles or alter their publisher, rubric,
status, content, slug or stored URL. Section deletion removes its placements,
preserving referenced articles. Existing category deletion rules remain unchanged.

## Saved-content admin preview

Saved category and section admin forms expose “Preview Guide Hub” when the
editor has the existing category, GuideSection, GuideSectionArticle and Post
view permissions (change permission also qualifies). The preview is an admin-only
GET/HEAD endpoint named `admin:classifier_category_guide_preview`, keyed by the
category primary key. Admin staff authentication and category object permission
checks apply. No permission is granted automatically and no new permission or
schema is introduced.

The endpoint uses the same `posts/guide_hub.html` renderer, shared rendering
context builder and public collection helper as the public category page. It
shows saved, publicly eligible content only; inactive sections/articles/categories
and unsaved form fields are not previewed. Catalog categories can preview their
prepared guide without switching presentation mode. Empty/inactive collections
show the existing empty state. Categories without a parent cannot be previewed.

The complete eligible article set must also be visible through the requesting
editor's existing PostAdmin queryset. Own-article editors can preview a collection
whose eligible articles they own; a mixed collection containing another
publisher's out-of-scope article returns 403 rather than a partial preview.
This check happens on every request, independently of preview-link visibility.

Preview responses use `X-Robots-Tag: noindex, nofollow`, a matching HTML robots
meta tag, private/no-store/no-cache response directives, an expired Expires header
and `Vary: Cookie`. The wrapper also applies these headers to admin login redirects
and handled 403/404/405 responses. POST is rejected; URL query fields do not change
saved data. Collection queries remain uncached and are reevaluated each time.

The preview has a saved-content notice and a link back to category admin.
Its canonical points to the existing public category URL; preview collection and
sharing metadata are suppressed, and analytics/adverts are disabled. Previews do
not create sitemap entries or public links. Article URLs, ownership and content
are not regenerated or saved. Public query parameters cannot enable preview mode.

## Category rendering

`PostListView` dispatches `guide_hub` categories to `posts/guide_hub.html` before
executing catalog filtering queries. Catalog categories retain their alphabetical
view, filters and separate paginated list. The guide uses the public collection
query below, section anchors based on primary keys, optional plain-text section
descriptions and stored article URLs. It never embeds full article content.
Missing stored article URLs render as unlinked titles without a URL backfill.

Guide category requests require the actual parent slug and active category
ancestry; otherwise they return 404. An active guide with no eligible sections
returns 200 with an explicit empty state. Guide-only sibling navigation excludes
inactive categories and is uncached. Legacy catalog navigation is unchanged.

The guide's `/list/` alias returns a temporary 302 to its existing main category
route for GET and HEAD, dropping query parameters. The redirect uses private,
no-store/no-cache response directives and an expired Expires header so switching
back to catalog mode restores `/list/` pagination without a permanent redirect.
Catalog `/list/` pagination is unchanged.
Guide query parameters do not apply catalog filters; existing canonical/robots
rules omit them from the canonical URL and mark query variants noindex.

Category title, H1, introductory rich text, metadata, breadcrumbs and configured
public origin are reused. Collection structured data includes each linked
eligible article once in first-appearance order, while repeated placements stay
visible in their sections. The displayed material count is the unique eligible
article count. A missing stored URL is omitted from structured data. Existing
catalog sitemap enumeration and all article routes/canonicals are unchanged.
Guide category sitemap entries additionally require active category ancestry,
matching the guide route. Inactive guides or active guides beneath an inactive
ancestor are omitted. This does not change legacy catalog ancestry behavior.

## Public collection query

`core.posts.guide_hub.get_public_guide_sections(category_id)` returns a list of
ordered `GuideSection` objects. Each section has a `public_articles` list of
ordered `GuideSectionArticle` placements with their posts already loaded.
The ordinary `articles` related manager remains unfiltered and must not be used
as the public collection. The category guide renderer uses this helper.

- Only active sections and posts with `status=True` are included.
- The hub category, the article's owning category, and every ancestor of each
  must be active. Eligibility uses database MPTT boundaries at arbitrary depth;
  inactive siblings or unrelated trees do not affect the result.
- Sections with no eligible articles are omitted. A missing or inactive hub
  returns an empty list. Eligible cross-category placements and repeated article
  references across sections are preserved.
- Both levels use `(sort_order, pk)` ordering. A populated collection takes two
  SQL queries regardless of section/placement count; section categories, posts
  and their owning categories are loaded in those queries. Photos and other
  article relations are outside this query contract.
- Reads are uncached, do not generate missing URLs and never save articles.
  Visibility changes are evaluated on every call; this is discovery eligibility,
  not a new access-control rule for the existing article detail view.
- Presentation mode is intentionally left to the caller to resolve. An active
  category can be queried independently of its default mode, allowing future
  site-specific presentation overrides without changing collection eligibility.

Migrations: `classifier.0015_guide_hub_foundation` depends on classifier 0014;
`posts.0035_guide_hub_foundation` depends on that migration and posts 0034.
They add the default presentation field and two tables without content backfill
or article updates. Reversing them removes Guide Hub configuration and
placements; existing categories and posts remain.

## Future site and language boundaries

The category field is a default, not permanent global presentation authority.
A future site-specific category presentation record can override it during
request resolution, falling back to `Category.presentation_mode` when absent.
The existing section and placement records retain stable primary keys and
foreign-key targets; no relationship relies on a title, slug, hostname or locale.

Different collections or ordering per site will need explicit ownership or
override records for sections and placements. Site membership alone does not
provide different orderings. That extension can reference existing section and
placement IDs without replacing the section-to-article relationship model.
Translated labels and translated-article selection remain separate future work.
No Site or Translation fields are introduced by this foundation.

The newer shared-backend direction has not been reconciled with the accepted
2026-09-06 separate-international-application ADR. This feature neither resolves
nor implements that architecture decision.
