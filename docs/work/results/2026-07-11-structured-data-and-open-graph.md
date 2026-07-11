# Structured Data And Open Graph Result

- Date: 2026-07-11
- Status: Complete

## Delivered

- Added site-wide `Organization` and `WebSite` JSON-LD with a `SearchAction` targeting `/search/?q=...`.
- Added reusable, safely serialized schema.org output for `BreadcrumbList`, `Article`, `NewsArticle`, `CollectionPage`/`ItemList`, and `Event`.
- Applied structured data to the homepage/base, post categories and details, news lists and details, and event lists and details.
- Added a dedicated branded 1200x630 AgroMega Open Graph image; content images continue to take precedence on post, news, category, and event detail pages.
- Removed manually interpolated Article JSON-LD so quotes and rich-text content cannot invalidate the JSON payload.

## Deferred

`Product`/`Offer` markup for adverts remains intentionally deferred until price currency, price validity, and availability are represented as dependable structured fields rather than presentation-only values.

## Verification

- `just check` passed with the repository's existing CKEditor and non-unique username warnings.
- 21 targeted post/category/home/news tests passed.
- Tests parse emitted JSON-LD and verify global site schema, SearchAction, NewsArticle, and the default Open Graph image.
