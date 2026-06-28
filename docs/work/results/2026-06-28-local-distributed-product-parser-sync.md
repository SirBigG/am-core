# Result: Local Distributed Product Parser Sync

- Date: 2026-06-28
- Related plan: `docs/work/plans/2026-06-28-local-distributed-product-parser-sync.md`

## Summary

Implemented the first low-cost local parser sync slice in `am-core`.

The main Django site now stays the source of truth for parser source configuration and product publishing, while in-process admin parsing is disabled by default. Trusted local workers can authenticate with parser worker tokens, lease active sources, submit parsed product results, and record failures.

## Delivered

- Added `ENABLE_IN_PROCESS_COMPANY_PARSING`, defaulting to disabled.
- Added `PARSER_MIN_CRAWL_INTERVAL_MINUTES`, defaulting to one day, so local workers do not re-parse recently crawled sources even if a source has a shorter interval.
- Added `PARSER_FAILURE_RETRY_MINUTES`, defaulting to one hour, so failed parser sources can recover sooner than successful daily crawls without immediate retry loops.
- Hid and guarded the legacy Django admin parser action and blocked the old admin parse form when in-process parsing is disabled.
- Extended `core.companies.Link` with parser source metadata, experiment labels, priority, crawl cadence, lease fields, and crawl result status fields.
- Extended `core.companies.Product` with parser source identity and `price_updated_at`.
- Added `ProductPriceHistory` for observed parsed prices.
- Added optional exact company latitude/longitude fields to support future shop map cards and variety availability/spread views.
- Added authenticated worker endpoints under `/api/parser/` using existing DRF database tokens plus the `companies.use_parser_worker_api` permission:
  - `GET /api/parser/sources/`
  - `POST /api/parser/sources/<id>/lease/`
  - `POST /api/parser/sources/<id>/results/`
  - `POST /api/parser/sources/<id>/failure/`
- Updated company/product templates so stale prices are not shown as current in related-product blocks, while company detail still keeps products visible.
- Replaced raw admin parser-map editing for companies and parser sources with minimal structured fields for product name and price XPath selectors.
- Improved automatic product-to-post matching so parsed products can link to active posts in the same category by exact title, title contained in the product name, token coverage, or existing full-text fallback.
- Added `link_product_posts` to backfill existing active products that still have no linked post.
- Added `run_local_parser_worker` for trusted laptops to pull sources, lease work, parse locally, and submit results or failures through the API.
- Added focused tests for worker auth, leasing, result upsert, price history, stale price hiding, failure submission, and disabled admin parser action.
- Hardened the first review findings:
  - parser leases and result/failure submissions now run under row locks and database transactions;
  - parsed products have a source/key uniqueness constraint;
  - parser submissions that miss price data preserve the previous accepted price;
  - admin/manual price edits refresh price freshness timestamps;
  - source listing respects each source crawl interval and the global minimum crawl interval;
  - source listing validates worker query limits and filters due sources in the database before slicing;
  - lease creation rechecks active and due state inside the row-locked transaction;
  - parser failures release leases without marking the source successfully crawled and use a shorter failure retry cooldown;
  - local workers do not convert uncertain result-submission network errors into parser failures;
  - parser attempts are recorded for success/failure visibility.

## Configuration

Create a dedicated service user for each trusted local worker machine, assign `companies.use_parser_worker_api`, then create its token at `/admin/authtoken/tokenproxy/`. Parser endpoints only use token authentication; normal browser sessions and ordinary user tokens without this permission cannot access them.

Local workers should send:

```http
Authorization: Token <token>
```

Run a local worker from a laptop with:

```bash
./manage.py run_local_parser_worker \
  --base-url https://agromega.example \
  --token "$PARSER_WORKER_TOKEN" \
  --category apples \
  --experiment apples-phase-1 \
  --limit 5
```

## Follow-Up

- Add the first apple parser source list and parser configs in admin.
- Consider a more formal service credential model if multiple non-household machines need access.
