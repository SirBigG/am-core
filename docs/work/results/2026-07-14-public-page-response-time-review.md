# Public Page Response-Time Review

- Date: 2026-07-14
- Scope: crawler-visible `am-core` HTML pages, with priority on post detail pages
- Trigger: Google Search Console reported a 30-day average response time of 382 ms
- Change type: read-only investigation; no application behavior was changed

## Executive Summary

The 382 ms crawler average is plausible and is not primarily explained by Docker-network database latency. A small live sample produced median TTFB values of approximately 385 ms for a post detail page, 404 ms for adverts, 508 ms for the homepage, and 516 ms for news. Local production-like request inspection found avoidable query multiplication, synchronous upstream I/O, expensive random ordering, writes during crawler-visible GET requests, and a development application server in the Compose startup path.

The highest-value sequence is:

1. Remove database writes from registry GET requests.
2. Align the local Compose startup with production Daphne and add request timing/query observability.
3. Remove repeated photo and category-tree queries from shared public templates.
4. Consolidate the post-detail query plan and cache recommendation/navigation data.
5. Add timeouts and caching to the news upstream calls.

These changes should be measured before adding broad full-page caching. Full-page caching needs special care because templates vary on authentication/cookies and post pages render CSRF-bearing comment UI.

## Evidence

### Live TTFB sample

Read-only `curl` requests were made from the review environment to the public site. The three-run medians were:

| Public page family | Median TTFB |
| --- | ---: |
| Homepage | 508 ms |
| Post detail | 385 ms |
| Advert list | 404 ms |
| Registry root | 319 ms |
| Company list | 350 ms |
| News list | 516 ms |

This is a small directional sample, not a substitute for server-side percentiles. Internet connection setup and route variance are included.

### Local request query sample

The local Docker stack used its existing database. Silk middleware was removed from the measurement because Silk records and explains queries itself. Requests were anonymous and made with Django's test client against the normal templates.

| Route family | SQL queries | Local elapsed |
| --- | ---: | ---: |
| Homepage | 58 | 139 ms |
| Post detail | 23 | 28 ms |
| Advert list | 5 | 8 ms |
| Company list | 3 | 6 ms |
| Event list | 3 | 6 ms |
| Category index | 53 | 28 ms |
| Parent category | 18 | 12 ms |
| Alphabetical post category | 10 | 12 ms |
| 50-item post list | 154 | 62 ms |

The database reported only a minority of the local elapsed time. Query round trips, ORM/model work, template rendering, image URL generation, and response construction are all part of TTFB even when PostgreSQL is nearby.

Current local data sizes relevant to the observed query plans were 3,267 active posts, 3,757 post photos, 1,639 adverts, 146 categories, and 26,608 registry varieties.

## Findings

### P1: Registry variety pages write every row during an HTTP GET

`core/registry/views.py:38-39` loops over every variety in the selected category and calls `save()` before reading the rows. The largest current categories contain 3,311, 3,150, 1,891, and 1,660 varieties. A crawler request to the largest category can therefore issue thousands of unnecessary updates before rendering.

Risk:

- Extreme TTFB and possible request timeout on the largest registry pages.
- Row locks, WAL generation, database I/O, replica/backup pressure, and contention caused by read traffic.
- Search crawlers can repeatedly trigger writes.

Shortest remediation:

- Delete the save loop from the view.
- If a derived field genuinely needs backfilling, do it once in a migration or management command.
- Add a regression test asserting that a GET performs no database writes and a bounded number of queries.

### P2: Local Compose does not match the production Daphne startup

Production runs Daphne. However, `../docker-compose.yml` starts `./bin/serve.sh`; `bin/serve.sh:4-5` runs migrations and then `manage.py runserver`. The Dockerfile's Daphne command is overridden by Compose and is not used by this local path. Django explicitly states that `runserver` is not designed for production.

Risk:

- Local performance and concurrency verification does not exercise the production ASGI server.
- Server-specific regressions or tuning mistakes can reach production without being reproduced locally.
- The production Daphne process count and saturation behavior remain unmeasured in this review.

Shortest remediation:

- Add a production-like Compose command or profile that runs Daphne with the same important production settings.
- Keep migrations as a separate deployment step rather than coupling them to web-server startup.
- Document and load-test the Daphne process/container count. If ASGI is retained, use database pooling rather than `CONN_MAX_AGE`; Django 6 recommends disabling persistent connections in async mode.
- Benchmark Uvicorn only as a controlled alternative with the same application code, process count, connection limits, and traffic mix. Do not infer an application-latency improvement from server microbenchmarks alone.

Reference: https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

### P1: Repeated `photo.first` template access creates large N+1 query sets

`core/posts/models.py:42-49` prefetches `photo`, but templates repeatedly call `post.photo.first`:

- `core/posts/templates/posts/helpers/object_list.html:4-9`
- `templates/index.html:235-240`
- `templates/index.html:270-275`

Calling `first()` this way does not reuse the prefetched collection in the observed query plan. The homepage executed 50 photo queries. A 50-item post list executed 144 photo queries and 154 total queries.

Shortest remediation:

- Prefetch ordered photos to a `to_attr`, or annotate/prefetch one primary photo explicitly.
- Resolve the primary photo once per post in Python and render that value without repeated related-manager calls.
- Add query-budget tests for 1-item and 50-item pages so query count stays constant as list size grows.

### P1: News pages block on an upstream HTTP request without a timeout or cache

`core/news/views.py:20-31`, `58-68`, `87-111`, and `126-133` call `requests.get()` synchronously without a timeout. Every news list/detail request and the news sitemap depends on the upstream service response. The live news list had the slowest sampled median TTFB at about 516 ms.

Risk:

- Upstream slowness directly becomes crawler-visible TTFB.
- An unresponsive upstream can occupy application workers for a long time.
- Repeated crawler requests repeat identical upstream work.

Shortest remediation:

- Add explicit connect/read timeouts and handled exceptions.
- Cache successful list/detail/sitemap payloads for a short bounded period, with stale-on-error behavior where acceptable.
- Record upstream duration and outcome separately from total request duration.

### P2: Post detail pages perform a fragmented query plan plus uncached random recommendation work

`core/posts/views.py:168-190` uses the default `DetailView` queryset and then separately loads the first photo, photo count, rubric, publisher, registry existence, and attribute schema. Template tags then query ancestors, sibling menu items, comments, products, adverts, and two random post sets.

The measured detail request used 23 SQL queries. Nine began from the category table. `core/posts/templatetags/post_extras.py:249-272` also runs two `ORDER BY RANDOM()` queries per detail page; the homepage has additional random ordering in `core/posts/views.py:47-52`.

Shortest remediation:

- Give `PostDetail` an explicit queryset with `select_related("rubric", "rubric__parent", "rubric__meta", "publisher", "country", "meta")` and an ordered photo prefetch.
- Reuse one computed ancestor/menu structure rather than querying it through several tags.
- Replace per-request random sorting with a cached rotating set, preselected IDs, or deterministic recommendations. Exclude the current post and prevent duplicate rows caused by joining multiple photos.
- Cache relatively stable related posts, adverts, and navigation fragments with explicit invalidation or short TTLs.

### P2: Category index rendering has a category-tree N+1 pattern

`core/posts/templates/posts/index_categories.html:2-27` calls `get_children` for each root and then for every child. The measured category index issued 53 category queries.

Shortest remediation:

- Load the active tree once and use MPTT's cached-tree utilities, or prefetch exactly the two displayed levels.
- Reuse/cache the same root navigation data in the header and footer. `templates/header.html:3` and `templates/footer.html:2` currently invoke the same database-backed tag separately on every uncached render.
- Add a fixed query-budget test for the full category page.

### P2: Crawler-visible advert detail requests perform a database write

`core/adverts/views.py:114-119` reads the advert, increments `views` in Python, and saves on every detail GET.

Risk:

- Every crawler hit adds a write to an otherwise cacheable page.
- Concurrent increments can be lost because this is a read-modify-write sequence.

Shortest remediation:

- Decide whether crawler views should count.
- If counts remain synchronous, use an atomic `F()` update and avoid refreshing the page object.
- Prefer buffered/asynchronous analytics if exact immediate counts are unnecessary.

### P2: The cache is process-local and there is no public HTML cache policy

`settings/settings.py:199-203` uses `LocMemCache`. It can reduce repeated work only inside one process and cannot coordinate across multiple web processes or containers. Public HTML responses also vary on Cookie and do not expose a server-side page cache in the reviewed configuration.

Shortest remediation:

- First remove query multiplication and introduce instrumentation.
- Then use a shared cache such as Redis for navigation, category trees, recommendations, and upstream news payloads.
- Consider anonymous page or reverse-proxy microcaching only after defining cookie, authentication, CSRF, invalidation, and stale-content rules. Do not cache authenticated pages as anonymous HTML.

### P3: Several list/sitemap paths materialize more data than necessary

- `core/posts/views.py:104-108` loads and sorts an entire category in Python. This may be acceptable for alphabetic catalogs but needs a size threshold and caching for large categories.
- `core/companies/views.py:11-17` has no pagination, though the current dataset is only 20 companies.
- Sitemap views rebuild their data on every request. They are natural short-TTL cache candidates after correctness is preserved.

## Recommended Delivery Order

### Phase 1: Safety and measurement

- Remove registry GET writes.
- Align the local performance profile with production Daphne and confirm the production process/container count.
- Add structured request timing with route name, status, total duration, query count/query duration in non-production sampling, and upstream duration.
- Establish p50/p75/p95 TTFB per route family and separate bot/user traffic.

### Phase 2: Query-count reductions

- Fix primary-photo prefetch/rendering.
- Cache/load the category tree once.
- Consolidate `PostDetail` relations, ancestors, and menus.
- Add query-budget regression tests.

Suggested initial budgets after implementation, to be confirmed by tests:

- Post list: no growth in query count between 1 and 50 posts; target under 12 queries.
- Homepage: target under 15 queries.
- Post detail without comments/registry row: target under 12 queries.
- Category index: target under 8 queries.
- Registry variety GET: zero writes.

### Phase 3: Avoid repeated expensive work

- Replace `ORDER BY RANDOM()` recommendations.
- Cache category/navigation/recommendation data in a shared cache.
- Add upstream timeouts, payload caching, and stale fallback for news.
- Cache sitemap responses for a bounded TTL.

### Phase 4: Controlled anonymous response caching

- Evaluate Nginx/Django caching for crawler-visible GET/HEAD responses only.
- Bypass on authentication/session cookies and private routes.
- Resolve CSRF/comment-form behavior before caching post-detail HTML.
- Add explicit cache purge/versioning for publication updates.

## Verification Plan For Follow-Up Implementation

- Run targeted Django tests in Docker.
- Add `CaptureQueriesContext` assertions with Silk disabled.
- Assert no write SQL on all public GET and HEAD routes, except explicitly approved analytics paths.
- Benchmark representative small and large categories with warm and cold caches.
- Load-test the chosen application server at expected and burst concurrency.
- Compare 7-day and 28-day Search Console crawler response time after deployment, but use server-side p50/p75/p95 as the immediate release signal because Search Console lags.

## Review Limits

- The live sample was intentionally small and taken from one client location.
- Production database query traces, CPU, worker saturation, disk I/O, cache hit rates, and Nginx upstream timings were not available.
- Production uses Daphne according to the operator; the repository's local Compose path still uses `runserver`, so local server/concurrency behavior differs from production.
- Local timings used existing local data and are directional; query counts are the stronger regression signal.

## Follow-Up Implementation

The application-level improvements from this review were implemented on 2026-07-16. See `docs/work/results/2026-07-16-public-page-response-time-improvements.md` for delivered changes, before/after query evidence, and verification results.
