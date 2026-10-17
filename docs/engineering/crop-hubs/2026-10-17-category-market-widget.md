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
The cache key version is v5. The preview uses existing responsive crop-card CSS.

The separate price block aggregates the same eligible offer cohort into nominal
min/max prices, offer/seller counts and latest timestamp per currency. Fixed prices
take precedence over minimum/maximum fields, as on the existing market. Null and
blank currency form one unknown group. There are no individual product cards.
A filtered primary-key subquery preserves the legacy window-based deduplication
before grouping. One aggregate query serves current ranges; a second groups valid
`ProductPriceHistory` observations by local day/currency over 30 calendar days.
Only products currently eligible contribute. Historical currency changes retain
the recorded currency; charts cover currencies present in the current overview.
Missing dates are not filled or interpolated. Two distinct dates are required for
an inline responsive SVG chart; a details table exposes exact daily values and
counts of distinct products. No new dependencies or assets are required.
The normalized `price_summary` remains unavailable: package/unit/purpose evidence
still does not support per-kg analytics or a comparable market price index.
Previously the block unconditionally displayed the unavailable message.

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

Price-overview follow-up verification: **107 tests pass** in Compose/PostgreSQL
(`core.posts.tests.test_category_market_widget`, `core.posts.tests.test_crop_hub`,
`core.companies`, with `settings.test_settings`). Tests cover currency separation,
fixed/range prices, current cohort eligibility, legacy deduplication, all offers
beyond the six-variety preview, historical day grouping and distinct counts,
invalid/old/future history exclusion, single-day table without a chart, actual SVG
rendering, empty/inactive sources and stable query count. Scoped flake8 and diff
checks pass. Local inventory has zero currently eligible market offers, so these
checks use disposable test fixtures; production prices/history remain unverified.

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
