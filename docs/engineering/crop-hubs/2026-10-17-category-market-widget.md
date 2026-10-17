# Crop-page Agromarket category widget

17 October 2026. This implements the user's replacement scope: aggregate one
explicit Agromarket category on the crop page and leave the market itself alone.
The earlier proposed shared identity filter was withdrawn; prior investigation
and read-only evidence remain locally archived outside this release's source diff.
Product matching/data reconciliation is a separate task.

## Configuration and behavior

Nullable `CategoryHub.market_category` references an existing Category with
SET_NULL deletion behavior. It is editable in Hub admin, the Category inline and
the existing permission-scoped Hub API. No categories are seeded or inferred.
Migration `classifier.0018_categoryhub_market_category` is additive and must run
before workers serve the new model. Existing hubs default to null.

With a selected public category, the crop page calls the unchanged
`market_offers().filter(category_id=selected_id)` and the existing `market_posts`
helper. Scope is the exact category, as on the ordinary market category route.
It renders total offer rows, distinct companies, distinct varieties, the latest
price timestamp, up to six varieties (title/ID ordering), and ordinary category
and variety links without `hub`. Raw package/product rows are counted as in the
market; no matching status, alias or new freshness policy is introduced.

The knowledge catalog, article ownership, guides and placements stay independent.
Featured knowledge articles receive ordinary offer links only if they have offers
in the configured market category. Per-kg analytics remain unavailable.
The company-count link opens the existing company directory category filter,
whose eligibility is intentionally unchanged and can differ from offer counts.

Null retains the existing strict hub block/scoped links for backwards
compatibility. An explicitly configured source with inactive ancestry hides the
widget and action instead of switching to another source. Clearing/deleting the
reference returns to the existing block. Changing the hub selects a new cache
snapshot immediately; offer changes retain the existing maximum five-minute TTL.
The cache key version is v3. The preview uses existing responsive crop-card CSS.

`core/companies` is byte-for-byte identical to the inspected base HEAD; the earlier
market, matching, seller and market-test edits from this chat were removed.
Existing strict scoped routes and publication-market actions remain unchanged.

## Validation

Local PostgreSQL 15 command from am-dev:

```bash
docker compose exec -T core python manage.py test core.posts.tests.test_category_market_widget core.posts.tests.test_crop_hub core.companies core.classifier.tests api.v1.content.tests.test_hubs api.v1.parser --settings=settings.test_settings --noinput
```

**185 tests pass** (5.184 seconds). Coverage includes widget/category-market
parity with prefixed review rows and separate packages; exact category scope;
independent knowledge catalog; ordinary links; cached source switching and null;
inactive source/ancestors; bounded preview/query count; existing product freshness;
empty state; source deletion preserving hub/sections; admin selection; nullable
API writes with permission checks; and all existing market/hub/parser behavior.
The additive migration runs in the disposable PostgreSQL test database.

Scoped flake8, migration consistency and diff checks pass. Migration 0018 was
also applied to the verified local Compose database (`db` / `agrodb`); no source
category was assigned. No production write, category assignment, permission
change, commit, push, merge or deployment is part of this implementation.

## Rollout and acceptance

Apply migration 0018 through the existing release process before serving workers.
Then select `market_category` on the intended hub. On production potato, category
2504 was previously read back as the ordinary market category; verify that target
again before any separately authorized configuration write. Preserve hub 1,
its four existing references, Guide sections/placements and source collection.

After configuration/cache expiry, compare the widget totals and preview offer
counts to that ordinary category's current market pages. Verify preview/category
links, desktop/mobile wrapping, an empty category and source changes. The general
market and `?hub` routes must retain their prior behavior. Clearing the reference
restores the old strict crop-page block; roll code back only through the existing
release process after considering the additive schema compatibility.
