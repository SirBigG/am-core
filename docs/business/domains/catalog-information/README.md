# Domain: Catalog Information

## Purpose

Catalog information is the main knowledge area of the product. It contains structured reference information such as plant varieties, diseases, and other catalog-like agricultural content.

## Actors

- Users who read catalog information.
- Content managers or administrators who create and maintain catalog records.
- Other domains that link to or categorize catalog content.

## Core Workflows

- Publish and maintain catalog records.
- Organize catalog records so users can discover relevant information.
- Connect catalog records with categories and possibly related content.

## Business Rules

- Catalog content is treated as important reference information, not short-lived social content.
- Token-authenticated integrations can read the shared post catalog and create posts owned by the token user.
- Integration updates require a token-authenticated staff user. Staff editors can update any post through the content API without changing its original publisher; non-staff tokens cannot use the post detail/update endpoint.
- Integration post creation derives the publisher from the credential and never trusts a publisher supplied in the request body.
- For categories with a public post-detail route, content API creation also
  persists the canonical URL in the same transaction before returning `201`.
  A new article can enter public search after index refresh without requiring
  a prior page visit or a second editorial save.
- Varieties, diseases, and similar catalog entities belong in this domain unless a more specific bounded context is created later.
- Category assignment likely affects how users find catalog information.
- Main-site post detail URLs use the post's current category and slug as the
  canonical path. After deployment of canonical redirects, old category or slug
  paths with the same post ID return HTTP 301 directly to that current path.
  GET and HEAD use the same rule; query parameters are omitted from the redirect.
- The global “Цікавинки на додачу” discovery block includes only active posts with images, prefers different broad category trees, excludes the page's current post, and avoids immediately repeating the four visible items when a visitor requests another set.
- Registry spreadsheet refreshes should preserve existing variety records and update them in place by variety title plus registry category.
- Active registry rows clear exclusion metadata when an existing variety is present in the active sheet.
- Excluded registry rows mark matching varieties as excluded and store the registry end date/year.
- Registry refreshes can be queued from the `Variety` Django admin by uploading a state registry workbook in `.xlsx` or `.ods` format.
- Queued registry refreshes are processed only by the `run_registry_import_jobs` Django management command.
- The command processes one registry import at a time; pending jobs wait while another import is marked running.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include draft, published, hidden, archived, or reviewed.

## Neighboring Domains

- Classification and taxonomy.
- Companies and shops, if products or company information links to catalog records.
- Diary and journals, if users refer to catalog records in personalized plant or field journals.

## Implementation Map

- Proposed structured catalog relations and plant-protection application rules
  are specified in the [AGRO-73 technical contract](../../../engineering/decisions/2026-11-15-catalog-relations-contract.md).
  This is a design awaiting independent review; typed application records and
  automatic related-catalog blocks are not implemented by that document.

- Editorial instructions: [Managing category pages, Crop Hubs and Guide Hubs](../../guides/category-pages-and-widgets.md).

- Guide Hub curation has a data foundation: categories can own ordered sections
  with ordered references to existing articles, including articles owned by
  other categories. The same article can appear in multiple sections without
  changing its ownership, content or canonical URL. Guide Hub categories render
  on their existing category URLs. Editors manage sections from category admin
  and ordered article references from each section's admin page. See the
  [data contract](../../../engineering/guide-hub-foundation.md).
- The public Guide Hub collection query excludes inactive sections, inactive
  articles and any hub or article category below an inactive ancestor (including
  the category itself). It omits sections with no eligible articles and preserves
  editorial ordering and cross-category references. Empty guides show a preparation
  message. Inactive guide categories and their descendants are unavailable through
  guide category routes; existing article detail access behavior is unchanged.
- Guide Hub editing requires explicit section and placement permissions in
  Django Admin. Article selection respects existing global or own-article
  permissions. Curation never changes article ownership, content or URLs;
  permission-scoped agent management is also available through the
  [hub management API](../../../engineering/api/hub-management.md).
- Authorized editors can preview saved, publicly eligible Guide Hub content from
  category and section admin. Unsaved edits and hidden content are excluded.
  Preview access requires category, section, placement and article visibility;
  it is denied if a full preview would include an article outside the editor's
  scope. Previews are noindex and uncached and do not change public presentation.
- Deleting guide sections with placements also requires placement-delete permission and visibility
  of the affected articles, including when deletion happens through category
  forms or category subtrees. Section audit history requires global article
  visibility because old log entries can reference removed articles.
- Guide sitemap entries follow active category ancestry. Guide list aliases use
  uncached temporary redirects so returning a category to catalog mode restores
  its paginated list.

- Django app: `core/posts`.
- Token-authenticated integration endpoints: `/api/content/posts/` and `/api/content/posts/<id>/`.
- Knowledge Engine can link an existing publication to a registry variety using
  the [registry publication API](../../../engineering/api/registry-variety-publication.md).
  The attachment preserves an existing link when the requested publication differs.
- Some variety-style public catalog URLs, such as `/cybulevi/sorty-cybuli/`, are rendered through post/category templates even when the content behaves like registry/catalog reference information.
- Registry-specific category and variety templates also exist in `core/registry`, especially for `/registry/` and registry browsing flows.
- Registry import code starts in `core/registry/parser.py`, with row layout definitions in `core/registry/parser_row_types.py`.

## Open Questions

- Why is this domain implemented in `core/posts`, and does the code still contain social/community post behavior?
- Which catalog entity types are currently supported besides varieties and diseases?
- Who is responsible for editorial quality and updates?
- Are catalog records user-generated, admin-managed, or both?
- Should registry variety descriptions from the state registry spreadsheet be stored in the current `Variety.description` field or in a separate structured reference-data model?
- Should the registry model support all six applicant, owner, and maintainer columns available in current state registry files?
- Should the registry import command run continuously with `--poll` under a supervisor, or only be invoked manually after an admin queues a refresh?

## Publication footer actions

Registry or explicitly market-linked catalog posts use a compact seller-offers
link after sources and before sharing, usefulness feedback and comments. It is
shown only when the shared market eligibility rules admit an offer. Labels use
the catalog title, and no claim of stock availability is made. Other publications
retain the legacy related-product behavior. Sharing remains independent of login
and analytics consent. Existing usefulness feedback remains visible to editors
in admin; its historical anonymous deduplication is not a unique-voter count.
See the [implementation and verification note](../../../engineering/testing/2026-09-05-publication-actions.md)
for the exact identity relation and existing limitations.

## Publication metadata

The canonical `title` names the cultivar, breed or other catalog entity and stays
in cards, breadcrumbs, matching and Agromarket. Optional direct `meta_title`
replaces the former `page_h1` and supplies both page title and H1, as well as social
and Article metadata. Optional `meta_description` supplies all description tags.
Empty fields independently fall back to the canonical title or a short plain-text
article excerpt. Editors configure these fields in “Метадані публікації”.

The content API reads and writes both fields and returns `resolved_metadata` for
integrations. Existing ownership and staff-update permissions remain unchanged.
Legacy related metadata is retained only as a migration archive and never used as
a fallback after an editor clears a direct field. See the
[API and migration contract](../../../engineering/api/publication-metadata.md).

## Reading navigation

Main-site publications build a table of contents in the browser from nonempty
`h2` and `h3` elements inside the article body, starting at three headings.
Comments, sources outside the body and related cards are excluded. Existing
heading IDs are retained; missing IDs receive collision-free fragment targets.
At widths of 1400px and above, the contents sit beside the unchanged text column.
On narrower screens, a sticky disclosure sits above the text and closes after a
section is selected; Escape closes it and returns focus to its summary.
The current section is highlighted and transitions account for the category menu.

Pages extending the main site's base template also offer “Нагору” after the
reader scrolls two viewport heights. It clears the mobile bottom navigation and
is hidden while cookie consent or a modal occupies the foreground. Scrolling
respects reduced-motion preferences and can be interrupted by user input.
These controls do not modify stored article HTML or community-app templates.

`CatalogEntity` stores a UUID, catalog kind and provenance independently of a post's title, category and URL. Several posts may point to one entity through the optional `Post.entity` link. An entity referenced by a post is protected from deletion. The initial migration leaves existing posts unlinked so editorial mappings can be supplied explicitly. This is the identity portion of AGRO-4 and the foundation for the AGRO-74 relation models.

### Structured relations

The shared catalog storage represents a relation as a stable record with immutable revisions and typed participants. A draft revision leaves the existing site release intact until a publisher selects an approved revision. An explicit withdrawal disables the record's releases and advances its eligibility epoch. Reinstatement requires separate review and leaves releases disabled until the publisher acts.

`Category.entity` accepts crop identities. A site and content locale can select an existing post or category as the presentation anchor for an entity. The selector record stores the editorial choice. The publication and visibility rules still belong to the corresponding site and content adapters.

The storage migrations seed the generic symmetric relation and cultivar-to-crop relation definitions. AGRO-85 owns the plant-protection application definition and its source-specific validation. Admin, API and public readers connect to the shared service in their respective tasks. See the [accepted relations contract](../../../engineering/decisions/2026-11-15-catalog-relations-contract.md).

Private relation access requires both a Django catalog permission and an explicit site grant. Each participant needs a separate grant. An optional post or category on that grant supplies the participant's label when the anchor still points to the granted identity. Private records are bound to their editorial site, and viewing or changing a record requires access to the participants in its history. Existing staff and superusers receive no site or participant grants from the migration. Private draft editing and submission use this policy; release decisions also require the publication policy.

In Django Admin, **Catalog → Relation records** opens the private list. Choose **Find a participant** to search authorized post and category labels and view their relations. To create a draft, select a relation schema and choose participants for its roles. Saving an edit creates a new revision. **Submit** moves the latest draft to editorial review. **Approve** and **Reject** require a reviewer permission and site capability. **Publish** and **Unpublish** require a publisher permission and site capability. Approval and publication check the selected content language and every participant’s current eligible presentation. **Archive** requires edit access and publisher capability on every site in the release history, and disables the releases. The revision history shows each version’s payload, source evidence, country, source digest, schema, roles and creation/review actors and times. This read-only history is available to authorized viewers and reviewers. The audit section records actions. A stale form requires a reload and another review of the current revision.

### Eligibility before releasing a relation

A relation participant must have an approved presentation selection for the chosen site and content language. A post selection also requires an enabled site publication, matching immutable review evidence for the current full material, a current publication date and visible scoped category ancestors. A crop category selection requires visible scoped configuration for its complete ancestry.

Content-language confirmation is attached to the reviewed material digest and actor/time. UI language is supplied separately by the request and does not create a content-language confirmation. Existing material with unknown language can qualify only through an explicit legacy publication on the recorded original site and a site policy allowing `und`. A changed body or source requires new approval evidence. SEO-only edits preserve that evidence.

The eligibility adapter introduced for AGRO-75 reads the current Post against immutable review evidence. It adds no existing publication memberships, grants or language approvals. The broader AGRO-4 PostText pending/live renderer remains a separate delivery. This adapter rejects a changed current material during a new relation release.

Publication actions for the generic `related_to` and `cultivar_of` schemas are available on the record page in Django Admin. Site grants carry separate `can_edit`, `can_review` and `can_publish` capabilities, paired with the corresponding Django permissions. A reviewer can review without draft-edit access. Shared review across released sites additionally requires `review_shared_relations` and explicit participant and review grants on each affected site. Domain-specific relation types require their own review adapter.

A new draft preserves the currently published revision. Unpublish targets the current site release and remains available when a participant’s publication becomes ineligible. The material digest covers title, body, sources, source, author and publisher. SEO-only metadata stays outside that digest. Editorial relation mutations and presentation selection changes acquire one transaction-scoped PostgreSQL advisory lock to coordinate their row-lock ordering. This conservatively serializes these mutations.

The private editorial API exposes authorized participant search, relation revisions, review and site release actions under `/api/content/catalog/`. It shares the Admin access policy, retains actor audit, uses record ETags for updates and durable request receipts for create/revision retries. API clients can inspect historical evidence with view access. See the [catalog relations API](../../../engineering/api/catalog-relations.md) for routes, request examples and pagination.

Plant-protection applications now attach immutable formulation, source, method, target and validity evidence to the shared relation revision. Grouped targets remain literal source text. Approval requires explicit domain and country authority, and site release rechecks known country-calendar validity and participant publication. The pilot stores no doses. Bulk import, public selection and automatic page blocks remain their separately owned deliveries. See the [application domain workflow](../../../engineering/api/plant-protection-applications.md).

Editors can prepare explicit catalog batches in **Relation records → Bulk operations** or the private content API. Preview shows creations, revisions, exact duplicates, status changes and errors. Apply is atomic for at most 50 items and records a durable actor/site receipt. Application source decisions use the same preview to withdraw a source version or reconcile a country quarantine. See the [bulk workflow](../../../engineering/api/catalog-batches.md).

The shared related-catalog selector follows one published relation revision for all filters. It checks every participant's current site, content language, material and category ancestry before counts, facets and pagination. A preparation appears once with its distinct eligible application methods retained as details. Current source withdrawal and country-calendar expiry apply on every read. No selection result is cached. Saved automatic blocks and page presentation remain separate deliveries. See the [selection contract](../../../engineering/api/catalog-selection.md).

Hub editors can prepare up to three ordered related-catalog blocks as an immutable configuration revision. Saving a draft leaves the active configuration unchanged. Preview uses current public facts; activation requires an explicitly authorized publisher and the reviewed preview. A block binds the hub's stable crop identity, site and content language. Its title, allowed filters, fixed conditions, layout and card limit are declarative. Explicit manual placement references are retained without editing the original Guide or market settings. Empty automatic slots stay automatic and hide their UI; manual restoration is an explicit off-mode for the later page renderer. See the [configuration workflow](../../../engineering/api/catalog-blocks.md).
