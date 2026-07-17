# Plan: Asynchronous Random Post Recommendations

- Date: 2026-07-16
- Status: Complete
- Owner: Codex
- Related domain: Catalog information
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Make the public “Цікавинки на додачу” block load independently and change meaningfully between requests without expensive database-wide random sorting or long-lived repeated selections.

## Non-Goals

- Replacing the category-specific related-post block.
- Adding Redis or another shared cache service.
- Building editorial ranking or recommendation analytics.
- Changing post publication rules.

## Current Understanding

- The block currently uses an hourly deterministic rotating ID window, so many pages show the same posts for a long time.
- It may include posts without useful images and can show several items from the same narrow category.
- The block is rendered synchronously on post, advert, company, and news detail pages.
- HTMX 2.0.10 is already built into the project but is currently loaded only by diary pages.

## Assumptions

- This global discovery block should prioritize variety and visual quality over same-category relevance; the separate related-post block already provides category relevance.
- Only active posts with at least one image should be eligible.
- A refresh action should avoid immediately repeating the four currently visible posts.
- Losing this nonessential block when JavaScript is unavailable is acceptable because primary page content and category-specific links remain server-rendered.

## Proposed Approach

- Change the existing template tag into a lightweight HTMX loader with a loading placeholder.
- Add a public GET fragment endpoint that returns the recommendation section and explicitly disables response caching.
- Cache the eligible `(post_id, category_id)` candidate pool for five minutes, but shuffle and select on every request.
- Prefer one post per broad category tree, then fill remaining slots from the shuffled pool only when fewer than four category trees are available.
- Exclude the current post and bounded prior IDs supplied by the refresh control.
- Fetch selected posts in a fixed random order with ordered photo prefetching and render their primary images.
- Add a refresh button that swaps the whole block and excludes the visible IDs.

## Risks And Unknowns

- Loading HTMX for this block adds a small client-side asset request on affected detail pages.
- LocMemCache candidate pools are per Daphne process; randomness remains per request, but newly published eligibility can lag by up to five minutes per process.
- Async recommendations are not present in the initial HTML for non-JavaScript clients.
- Pure randomness does not guarantee editorial quality; image presence and category diversity are initial quality guards.

## Test Strategy

- Verify loader markup and current-post exclusion URL on the post detail page.
- Verify fragment responses contain four unique, active, imaged posts where data permits.
- Verify current and previously displayed IDs are excluded.
- Verify selection prefers distinct categories and does not use `ORDER BY RANDOM()`.
- Verify response cache headers prevent a random selection from becoming sticky.
- Run targeted post, advert, company, news, CSP, template-lint, and static-build checks.

## Documentation Updates

- Add a dated result artifact with the delivered selection rules, query behavior, and verification.
- Update catalog domain documentation only if the implementation establishes a durable discovery rule beyond this block.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
