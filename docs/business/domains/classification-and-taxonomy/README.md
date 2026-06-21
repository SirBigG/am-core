# Domain: Classification And Taxonomy

## Purpose

Classification is the shared tree of categories used by other AgroMega core project areas. It gives the system a common taxonomy for grouping and finding business content.

## Actors

- Administrators or content managers who maintain the category tree.
- Other business apps that assign their records to categories.
- Users who browse, filter, or search content through categories.

## Core Workflows

- Create and maintain a hierarchical category tree.
- Attach categories to records in neighboring domains.
- Use the tree for navigation, filtering, search, or content organization.

## Business Rules

- Categories are hierarchical.
- Categories are shared infrastructure for other domains, not only a standalone content area.
- Changes to the tree can affect multiple business apps.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include active, hidden, archived, or draft categories.

## Neighboring Domains

- Catalog information.
- Advertising marketplace.
- Companies and shops.
- Events calendar.
- Any other app that uses categories for discovery or organization.

## Implementation Map

- Django app: `core/classifier`.

## Open Questions

- Who is allowed to create, reorder, rename, or delete categories?
- Are categories localized?
- What happens to existing records when a category is moved or removed?
- Which business apps depend on this taxonomy today?
