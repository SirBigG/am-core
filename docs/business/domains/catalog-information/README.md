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
