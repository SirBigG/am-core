# Plan: Public Page Response-Time Improvements

- Date: 2026-07-16
- Status: Complete
- Owner: Codex
- Related domain: Catalog information and all crawler-visible public web surfaces
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`
- Related investigation: `docs/work/results/2026-07-14-public-page-response-time-review.md`

## Goal

Reduce avoidable Django request work on public pages, especially post detail and catalog pages, while preserving rendered content and current user-visible behavior.

## Non-Goals

- Replacing production Daphne with another ASGI server.
- Adding Redis, a CDN, or reverse-proxy HTML caching.
- Redesigning public pages.
- Changing whether advert detail visits count as views.
- Reworking the external news service itself.

## Current Understanding

- Production uses Daphne; local Compose currently uses Django `runserver`.
- Local measurements found 58 queries on the homepage, 23 on a post detail, 53 on the category index, and 154 on a 50-item post list.
- Repeated `post.photo.first` template access bypasses the useful effect of the existing photo prefetch.
- Category rendering repeatedly queries tree children.
- Registry variety list GET requests save every matching variety.
- News pages perform synchronous upstream requests without explicit timeouts or caching.
- Post detail pages issue fragmented relation/navigation queries and per-request random recommendation queries.

## Assumptions

- Public HTML and URL behavior should remain stable.
- Existing advert view counting should remain, but the update may become atomic.
- The existing cache backend can support bounded best-effort caching in this pass; shared cross-process caching is a separate infrastructure decision.
- Short news timeouts and short-lived successful-response caching are acceptable as long as errors remain handled and stale data is not retained indefinitely.

## Proposed Approach

- Remove the registry save loop and add a regression test proving public registry GET requests do not write.
- Prefetch ordered post photos into a dedicated attribute and make templates resolve the primary photo once.
- Load/cache category navigation and displayed tree levels without per-node queries.
- Give post detail an explicit relation/prefetch plan and reduce repeated category/menu work.
- Replace database-wide random sorting with bounded, cacheable recommendation selection that avoids duplicate post rows.
- Make advert view increments atomic without changing the visible counter behavior.
- Centralize news HTTP retrieval with connect/read timeouts, short cache TTLs, and safe error handling.
- Add query-budget and behavior tests around the affected routes.

## Risks And Unknowns

- Template changes can accidentally suppress images or alter ordering.
- Cached navigation/news data can briefly lag updates; TTLs must stay bounded.
- LocMemCache is per process, so cache effectiveness will vary with Daphne process count.
- Comment rendering is third-party code and may keep some post-detail queries outside this pass.
- Query budgets must avoid dependence on Silk and development-only middleware.

## Test Strategy

- Targeted view/template tests for posts, registry, adverts, classifier, and news.
- Query-count tests comparing small and large post lists to catch N+1 growth.
- Capture SQL during registry GET and assert no `UPDATE`, `INSERT`, or `DELETE` statements.
- Mock news HTTP calls to verify timeout arguments, caching, upstream failure, and 404 behavior.
- Run static/template lint where changed templates require it.
- Re-measure representative routes against the local Docker data with Silk excluded.

## Documentation Updates

- Update `docs/work/results/2026-07-14-public-page-response-time-review.md` with corrected production Daphne context.
- Add a dated implementation result under `docs/work/results/` with before/after query evidence and remaining follow-ups.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
