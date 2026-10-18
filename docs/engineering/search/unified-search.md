# Unified search: core resources

Implemented locally on 2026-10-18; no production rollout has been performed.
The source inventory and previous behavior are recorded in
[the initial investigation](2026-10-18-unified-search-investigation.md).

## Ownership and public contract

`core.search` owns a derived PostgreSQL index and `/search/` presentation.
Source models, canonical pages, permissions and marketplace identity remain
owned by their existing apps. The route name remains `post-search-list`.

Supported resource types are catalog posts, categories including existing hub
destinations, adverts, market identities, companies and events. Post tags are
searchable aliases. On 2026-10-18 the user removed diaries and the variety
registry from search: their documents, filters, source triggers and registry
aliases are excluded. The source sections and their data remain unchanged.

News and community are not integrated in this slice. No external requests or
forum-database queries are made by the search request or indexer. The index
represents this application's database; it does not invent site membership for
legacy content or include the separate international application.

The default page mixes resources and provides type filters with counts. Counts
are computed after visibility filtering, before pagination; type navigation
retains the query. Equal scores sort by resource type and source ID. All search
responses are uncached and retain `noindex,follow`. Empty queries return no
resources. Query whitespace is collapsed and length is bounded to 255 characters
on both server and form. Invalid resource types return 404. An unbuilt index has
a distinct preparation state, rather than claiming there are no matches.

## Matching and ranking

The document identity is `(generation, resource_type, source_id)`. A document
contains a local canonical URL, title, normalized title, plain summary, normalized
body, aliases, taxonomy, weighted `tsvector` and indexing timestamp. Private
parser configuration, contacts, editorial fields and diary items are excluded.
HTML is stripped and excerpts are escaped by Django; query text is never used
as raw SQL or trusted HTML. Invalid/nonlocal URLs are skipped during indexing.

Normalization uses NFKC, case folding, common apostrophes/dashes and whitespace.
The `simple` text-search configuration preserves Ukrainian and Latin tokens.
Weights start with title A, aliases/taxonomy B, summary C and body D. Ranking
uses the stored vector directly. It does not rebuild a vector from its textual
representation during each query.

Candidates use `@@`, exact title, and for queries of at least three characters,
title substring and trigram similarity operators. The GIN indexes support the
FTS and trigram paths. Exact titles rank above title substrings, then full-text
matches, then fuzzy-only matches. Within each tier the score combines normalized
text rank and title similarity. Fuzzy matching is title-only; it does not change
catalog or product identity and does not scan every body with `icontains`.

This is lexical search with bounded fuzzy matching, not Ukrainian morphology,
transliteration or a curated agricultural synonym dictionary. Quality evaluation
on a larger relevance corpus and production-scale load remain later gates.

## Live eligibility

`sources.eligible_sources` applies correlated source `EXISTS` conditions in SQL
before counts and pagination. A stale projection cannot expose a deleted source,
hidden post/category ancestry, future post, expired advert, inactive company,
or ineligible market identity, even if the worker stops.

- Posts follow `crop_hub.public_posts`, including active ancestors, publication
  date and the existing nonempty canonical URL requirement.
- Categories follow public ancestry and exclude the artificial taxonomy root.
- Adverts use an aware current-time cutoff and `ADVERT_ACTIVE_DAYS`; a nullable
  category is allowed, a hidden assigned category is not. Sitemap retention
  does not extend the search lifetime.
- Market entries follow `market_offers`, additionally requiring strict public
  post ancestry and no future price timestamp. One result represents a post,
  not an individual seller. Eligible product names are searchable aliases.
  Only the page's current eligible offers are hydrated; seller counts and price
  ranges are computed live and currencies remain separate. Price expiry removes
  the market result without waiting for an indexing job.
- Events require `status=True`; default search selects events whose stop time
  has not passed. `archive=1` replaces these with past events. This parameter
  affects events only.

New/edited public text, aliases and newly eligible market identities are
eventually consistent with the worker. Live checks do not promise immediate
text refresh. The projection may still match a formerly eligible product alias
until the market scope refreshes; prices and visibility always use live rules.

## Durable invalidation and concurrency

Database triggers installed by the search migrations cover ORM saves,
`QuerySet.update`, bulk creates/updates, raw SQL, deletes and truncation. The
dependency map is explicit in migration `0002_source_invalidation`: changes to
posts/tags also invalidate market, category changes invalidate
dependent posts/adverts/market, company changes invalidate market, and public
geography/metadata/type changes invalidate their dependent projections.
Counter-only changes to post hits and advert views are ignored.

`SearchDirtyScope` coalesces each `(resource_type, transaction_id)` with a
sequence revision. Independent source transactions do not contend on a shared
dirty-scope row. Within a transaction a new mutation advances the revision.
The queue commits or rolls back with its source write.

The worker groups pending records by resource type, reads current source state
and atomically replaces the affected scopes. It deliberately rebuilds an affected
type, rather than claiming row-level incremental indexing. This favors correct
dependency fan-out at current scale; measure write/rebuild load before expansion.

Only indexers take a transaction-scoped advisory lock. Source writers do not
take it. The worker deletes exactly the queue IDs and revisions it observed,
not a sequence high-water mark. An older uncommitted transaction or a change
arriving during projection building remains queued for a later pass. Jobs carry
no stale content payload that could overwrite a newer source version.

A full rebuild creates a fresh generation, builds all types and switches the
active pointer in one transaction. Failure preserves the previous generation
and the queue. Old generation rows are removed in the same transaction.
Ordinary concurrent source edits can change totals between requests; pagination
does not provide a frozen multi-request snapshot.

The watch command polls every two seconds and performs full reconciliation every
300 seconds. Reconciliation repairs missed/manual changes and time-dependent
eligibility not represented by a new write. It is not a visibility cache. A
failed refresh rolls back and is retried; logs contain the failure. A coarse
scope rebuild can be expensive under sustained bulk ingestion and must be
measured before production enablement.

## Local operation and recovery

From the `am-dev` workspace:

```bash
docker compose -f docker-compose.yml exec core python manage.py migrate
docker compose -f docker-compose.yml exec core python manage.py sync_search_index --rebuild
docker compose -f docker-compose.yml up -d --build search_index
docker compose -f docker-compose.yml exec core python manage.py search_index_status --skip-checks
docker compose -f docker-compose.yml logs --tail 50 search_index
```

The Compose `search_index` service shares core dependencies and mounts only
the application source. It does not expose a port. It runs independently from
the web process and retries until startup migrations finish. Restart it after
Python changes; it is not an autoreloading web server. To apply only pending
scopes manually, run `sync_search_index` without `--rebuild`.

Status reports readiness, generation, last applied timestamp, document counts
and pending transaction counts per resource type. Document counts include
potentially eligible scheduled/expired records; they are not public result
counts. They must not be interpreted as active adverts or fresh market offers.

If the worker fails, keep the current generation, inspect its logs and retry
the pending refresh. Use `--rebuild` for a complete repair. Never truncate the
source tables or clear the queue to hide an indexing failure. Full rebuilds
roll back safely; the command does not mutate source content.

`UNIFIED_SEARCH_ENABLED=0` restores the legacy route implementation; the old
post vector and trigger are retained for this rollback. Legacy ranking and
post-only coverage remain, but its selector now also uses `public_posts()`:
inactive/future posts and hidden category ancestry remain absent. It shares
input bounds and whitespace cleanup with indexed search, skips navigation
statistics, and receives the same no-store headers from the route wrapper.
It does not query the search-index tables, so it works before backfill and
while the indexer is unavailable. The setting defaults
to `1` for local use. Before any future rollout, explicitly set it to `0`,
verify PostgreSQL/extension privileges, apply migrations including `pg_trgm`,
build and reconcile, start the worker, validate results, then enable and read
back. This document grants no deployment authority. Installing on existing
populated deployments needs a separately reviewed schema/backfill window.

Search statistics record only the initial unfiltered, nonempty search request;
page, type and archive navigation do not add duplicate search events. No
fingerprint is invented. Search query retention and aggregate analytics remain
separate operational work.

## Initial local verification on 2026-10-18

The figures below describe the initial eight-type build, before the user removed
diaries and registry from the search scope later the same day.

- Fresh PostgreSQL test database: **693 tests passed**, including 34 search
  tests, two of which use real concurrent connections. Coverage includes all
  types, title/alias/product matches, stale visibility, prices/currencies,
  bulk/raw SQL invalidation, deletion, failed rebuild, concurrent writes and
  an old transaction committing during a worker snapshot.
- The metadata migration test now restores all captured leaf migrations after
  rollback, including dependent search schema and triggers.
- `flake8 core api settings` passed. Bare repository-wide `flake8` also scans
  pre-existing gitignored `var/agents-work` scripts and fails on those scripts;
  no unrelated local analysis files were changed.
- `makemigrations --check --dry-run` reports no changes.
- Frontend build and local collectstatic passed. Existing Sass deprecation,
  CKEditor, nonunique email and legacy naive-time warnings remain.
- Browser through local Nginx: mixed results, company filtering and 390 px
  layout checked; measured document width equals viewport width (no horizontal
  overflow). Public market/advert states are covered by fixtures because the
  local snapshot contains no fresh eligible offers/adverts.
- Local derived index: 5684 documents; worker status ready with no pending
  changes. This is not a production inventory.
- Seven fixed queries, one warmup plus five measured iterations each, including
  counts and first 20 ORM results: p95 **39.44 ms**. Representative `картопля`
  `EXPLAIN ANALYZE` used both GIN indexes, with SQL execution **6.10 ms**.
  Measurements exclude HTTP rendering, use a small local dataset, and are not
  a concurrent load test or production acceptance.

No commit, push, release or deployment was performed as part of this slice.

## Scope correction on 2026-10-18

Migration `0004` removes the two retired document/queue types and their source
triggers, and queues refreshed post/market projections to remove registry aliases.
A local full rebuild applies the six-type scope. Runtime eligibility also excludes
retired types in stale generations; their old filter URLs return 404. Tests cover
absence from the index, filters, stale results and invalidation queue. Concurrency
tests now exercise adverts instead of diaries. No source content is deleted.

After the correction: 695 tests passed on a fresh local PostgreSQL test database;
application lint and migration consistency checks passed. Nginx readback returned
HTTP 200 with neither removed filter, and the local index contained zero diary
or registry documents. The worker was restarted with the six-type scope. No
deployment was performed.

## P1 remediation verified on 2026-10-18

Content API creation now persists the canonical URL for routable post categories
after the first insert assigns the PK, within the existing atomic create
transaction. It returns the saved URL in its `201` response. This fixes newly
created posts being projected but rejected by the live saved-URL requirement.
No source-data backfill or change to existing canonical URLs was performed.

Six permanent tests in `core/search/tests/test_release_regressions.py` cover
API response/detail, queue refresh and rebuild without manual URL repair,
read-only search rendering, future/inactive/hidden-ancestor exclusion in both
flag modes, schema-independent fallback, bounded input/cache headers, navigation
statistics and whitespace queries. The two original review repros pass unchanged.

Final fresh-DB suite: **701 tests passed**, application lint and migration
consistency checks passed; temporary production static build passed and matched
the existing CSS artifact. Real loopback HTTP checks passed for both flag modes
and normal/1000-character queries, with no-store/noindex; local Nginx returned
200 without the retired resource filters. Production rollout, DB-role acceptance,
load testing and release revision/CI verification remain separate gates.
