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
- Varieties, diseases, and similar catalog entities belong in this domain unless a more specific bounded context is created later.
- Category assignment likely affects how users find catalog information.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include draft, published, hidden, archived, or reviewed.

## Neighboring Domains

- Classification and taxonomy.
- Companies and shops, if products or company information links to catalog records.
- Diary and journals, if users refer to catalog records in personalized plant or field journals.

## Implementation Map

- Django app: `core/posts`.
- Some variety-style public catalog URLs, such as `/cybulevi/sorty-cybuli/`, are rendered through post/category templates even when the content behaves like registry/catalog reference information.
- Registry-specific category and variety templates also exist in `core/registry`, especially for `/registry/` and registry browsing flows.

## Open Questions

- Why is this domain implemented in `core/posts`, and does the code still contain social/community post behavior?
- Which catalog entity types are currently supported besides varieties and diseases?
- Who is responsible for editorial quality and updates?
- Are catalog records user-generated, admin-managed, or both?
