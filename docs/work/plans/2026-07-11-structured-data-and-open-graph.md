# Plan: Structured Data And Open Graph Coverage

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: catalog information, events calendar, publishing
- Related decisions: none

## Goal

Add valid schema.org coverage and a reliable social sharing image for public home, category, article, news, and event pages.

## Non-Goals

- Product/Offer markup until advert price and availability semantics are confirmed.
- Changes to private, search-result, or account pages.

## Current Understanding

The base template has canonical and partial Open Graph metadata. Post details contain manually assembled Article JSON-LD, while category, news, and event pages have no structured data. Some public templates output an empty `og:image`.

## Proposed Approach

- Add safe JSON-LD template tags backed by Python serialization.
- Emit Organization and WebSite/SearchAction site-wide.
- Add BreadcrumbList to category and post pages, NewsArticle to news details, Event to event details, and CollectionPage/ItemList to public lists.
- Use the existing 1244x700 homepage hero as the default OG image and preserve page-specific images.

## Risks And Unknowns

- Remote news payloads can have missing dates/images; markup must omit absent values.
- Category query variants are noindex and should not create misleading canonical item lists.

## Test Strategy

- Unit-test JSON serialization and schema shapes.
- Render targeted public pages and verify OG fallback and JSON-LD output.

## Documentation Updates

Write a result artifact with delivered coverage and deferred Product/Offer work.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
