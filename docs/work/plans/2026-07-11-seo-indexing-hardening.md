# Plan: SEO And Indexing Hardening

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: Public content discovery
- Related decisions: None

## Goal

Make canonical, robots, Open Graph, and sitemap output reliable and consistent for search crawlers.

## Non-Goals

- Adding structured data for every content type.
- Changing which public filtered or paginated catalog pages deserve dedicated landing pages.
- Changing advert sitemap retention rules.

## Current Understanding

The base template emits canonical and robots metadata. Query variants and search results are noindex. Public content is split across main, advert, and news sitemaps.

## Assumptions

Account, authentication, feedback, and content-creation routes should not appear in search results. Public content lists and detail pages remain indexable.

## Proposed Approach

- Centralize normalized public URL construction.
- Make private/workflow routes noindex while retaining crawlable links.
- Make sitemap generation safe with empty datasets and render real optional timestamps.
- Stop claiming the remote news sitemap changes on every request.
- Use absolute canonical URLs for default Open Graph metadata.

## Risks And Unknowns

Over-broad route matching could hide public content, so private path rules will use explicit prefixes and tests.

## Test Strategy

Add focused rendering tests for robots, canonical/Open Graph URLs, empty sitemap data, timestamps, and trailing-slash host configuration.

## Documentation Updates

Record implementation and verification under `docs/work/results/`.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
