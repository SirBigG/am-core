# Plan: SEO And Homepage Performance Baseline

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: Catalog information and all public web surfaces
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Give every public HTML response a stable self-referencing canonical URL, prevent search/query variants from indexing, deduplicate the main sitemap, reduce homepage inline CSS, improve homepage image loading hints, and give versioned static assets a one-year immutable cache lifetime.

## Non-Goals

- Redesigning the homepage.
- Changing media-file cache policy.
- Introducing a new image service or font family.
- Making filtered or paginated URLs independently indexable.

## Current Understanding

- `base.html` currently has an empty canonical block and a large inline style block.
- A few templates override canonical or robots metadata inconsistently.
- `SiteMap` assembles URLs without deduplication.
- Homepage-specific CSS is also inline despite an existing `index.scss` build entry.
- Live S3 object parameters currently apply a short shared cache policy.

## Assumptions

- `settings.HOST` is the authoritative public origin.
- Query-string variants should canonicalize to the same path without the query.
- All query-string pages are non-indexable, including pagination and current/future filters.
- The first available homepage content image is important; subsequent content images are lazy-loaded.

## Proposed Approach

- Add reusable template tags for canonical URLs and robots policy, then render both from `base.html`.
- Preserve template override blocks while making the defaults complete.
- Deduplicate sitemap entries by normalized URL and standardize the homepage with a trailing slash.
- Move base/homepage inline rules into the existing SCSS entries and rebuild static output.
- Add eager/high-priority hints to the first homepage image and lazy loading plus responsive candidates to lower images where source data permits.
- Apply long immutable caching only to the static storage backend.

## Risks And Unknowns

- Some pages may intentionally use query strings for non-filter state; the requested blanket query policy still makes these non-indexable.
- Existing custom canonical overrides may conflict and must be removed or aligned.
- Responsive source generation depends on whether the image is routed through imgproxy.

## Test Strategy

- Template-tag unit tests for canonical normalization and robots decisions.
- View tests for homepage, search, pagination/filter metadata, and sitemap uniqueness.
- Settings test for static-only immutable cache configuration.
- Static build plus targeted Django tests.

## Documentation Updates

- Record implementation and verification under `docs/work/results/`.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
