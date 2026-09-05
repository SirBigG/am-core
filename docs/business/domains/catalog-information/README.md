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
- Varieties, diseases, and similar catalog entities belong in this domain unless a more specific bounded context is created later.
- Category assignment likely affects how users find catalog information.
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

- Django app: `core/posts`.
- Token-authenticated integration endpoints: `/api/content/posts/` and `/api/content/posts/<id>/`.
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
