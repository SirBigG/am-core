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
- A main crop category can own an admin-managed Category Hub. It connects existing variety, disease, pest and growing categories and a curated guide collection through explicit references, including across legacy taxonomy branches. The landing page does not require source articles or catalogs to be moved or copied.
- Hub knowledge counts and market destinations derive from those category references. Market cultivar scope uses only the configured variety subtree; unrelated records under a broad legacy parent are excluded.
- Staff agents with explicit model permissions can manage hub and Guide Hub configuration through the [content API](../../../engineering/api/hub-management.md). Taxonomy creation and reparenting remain separate admin operations.
- The token-authenticated integration API exposes only active categories and preserves the complete hierarchy recursively.
- Categories are shared infrastructure for other domains, not only a standalone content area.
- Changes to the tree can affect multiple business apps.
- Concrete post categories can own structured attribute schemas. These schemas describe category-specific facts such as variety traits, illness traits, breed traits, or numeric intervals.
- Category attribute schemas can include public fields for user-facing filters and internal fields for admin or service workflows.
- Structured post attribute data should be preserved when a post changes category, but public filters should only use values indexed for the post's current category.

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
- Token-authenticated integration endpoints: `/api/content/categories/tree/` and `/api/content/countries/`.

## Open Questions

- Who is allowed to create, reorder, rename, or delete categories?
- Are categories localized?
- What happens to existing records when a category is moved or removed?
- Which business apps depend on this taxonomy today?
