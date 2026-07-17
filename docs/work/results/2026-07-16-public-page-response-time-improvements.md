# Public Page Response-Time Improvements

- Date: 2026-07-16
- Status: Complete
- Related plan: `docs/work/plans/2026-07-16-public-page-response-time-improvements.md`
- Related investigation: `docs/work/results/2026-07-14-public-page-response-time-review.md`

## Outcome

Implemented the application-level improvements identified in the public-page response-time review without changing the production Daphne server or adding infrastructure.

Delivered changes:

- Removed per-variety database writes from registry list GET requests and added a no-write regression test.
- Prefetched ordered post photos into a dedicated attribute and reused one primary-photo lookup in public list/home/detail templates.
- Loaded the category tree once for the category index and cached shared root navigation for the header and footer.
- Consolidated post-detail relations, photo access, category ancestors, and public attribute choices.
- Replaced PostgreSQL random sorting with deterministic hourly rotating ID windows. Dataset signatures prevent cached IDs from surviving row replacement.
- Excluded the current post from detail-page related/random recommendations.
- Made advert view increments atomic with an `F()` update while preserving the rendered counter behavior.
- Centralized news API JSON retrieval with explicit connect/read timeouts, bounded successful-response caching, invalid-JSON handling, and safe upstream failure behavior.

## Before/After Evidence

Measurements used the existing local PostgreSQL data, Django's test client, Silk middleware excluded, and the production-default LocMem cache for cold/warm comparisons. Timings are directional; query counts are the stronger evidence.

| Route family | Before | After cold | After warm |
| --- | ---: | ---: | ---: |
| Homepage | 58 queries / 139 ms | 12 / 112 ms | 9 / 17 ms |
| Post detail | 23 / 28 ms | 20 / 34 ms | 12 / 12 ms |
| Category index | 53 / 28 ms | 2 / 11 ms | 1 / 9 ms |
| 50-item post list | 154 / 62 ms | 9 / 22 ms | 7 / 15 ms |

The cold post-detail path builds two bounded recommendation caches, so its first-request query reduction is modest. Warm detail requests meet the original 12-query target and avoid database-wide random sorts.

## Verification

- 84 targeted Django tests passed across posts, registry, adverts, classifier, news, feature flags, rotating selection, and public CSP pages.
- Targeted Flake8 passed for every changed Python implementation/test file.
- `git diff --check` passed.
- Targeted djLint passed for all five changed templates.
- The complete Django suite ran 412 tests. It retained two unrelated baseline failures in untouched code: a stale profile dashboard copy assertion and feedback success rendering without an HTTP request context.
- Whole-project Flake8 remains blocked by pre-existing indentation errors in `content_refresh_runs/`; whole-project template lint remains blocked by the existing repository-wide template backlog. Changed files pass targeted checks.

## Operational Notes

- Production remains on Daphne. Switching ASGI servers was intentionally excluded because the measured bottlenecks were application/query work and synchronous upstream I/O.
- LocMemCache is per process. Each Daphne process will build its own navigation, recommendation, and news entries; a shared cache remains a possible infrastructure follow-up.
- Root navigation can lag category edits for at most one hour. Recommendation sets rotate hourly and successful news payloads cache for five minutes by default.
- News timeouts can be tuned with `NEWS_API_CONNECT_TIMEOUT`, `NEWS_API_READ_TIMEOUT`, and `NEWS_API_CACHE_TTL`.
- No migration or deployment-time data operation is required.

## Final Risk Review

No new P0-P2 correctness, concurrency, migration, or recovery findings were found. Atomic advert increments address the only changed concurrent write path. Cache failures degrade to recalculation or an empty news response rather than blocking the request indefinitely.
