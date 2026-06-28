# Plan: Local Distributed Product Parser Sync

- Date: 2026-06-28
- Status: Draft
- Owner: TBD
- Related domain: Companies And Shops, Catalog Information, Classification And Taxonomy
- Related plans:
  - `docs/work/plans/2026-06-28-organic-search-phase-1.md`
  - `docs/work/plans/2026-06-28-knowledge-engine-product-parser-integration.md`

## Goal

Build a low-cost parser workflow for the first commercial SEO experiment, starting with apples, where the main AgroMega site remains the source of truth for parser configuration and published product data while local laptops do the heavy parsing work.

The main server should let admins configure category-based parser sources, let trusted local worker machines sync those configs, and accept parsed product results back into the server database without running Selenium/browser parsing on the production web process.

## Non-Goals

- Do not deploy a paid always-on knowledge-engine server for Phase 1.
- Do not require Redis, a managed queue, or a new database service yet.
- Do not run multi-browser parsing from Django admin on the main site.
- Do not make public pages depend on local worker availability.
- Do not expose parser configs or result ingestion to unauthenticated users.
- Do not build a full marketplace monetization workflow in this phase.

## Current Understanding

`am-core` already has legacy company/product parser code:

- `Company.parser_map` and `Link.parser_map` store XPath parser configuration.
- `Link` stores source URL, company, category, active flag, last crawl time, and last crawl status.
- `core.companies.parser` can fetch pages with `requests` and can use Selenium/Firefox.
- Django admin currently exposes a `parse_link` action that calls `parse_many_links_with_same_browser`.
- Parsed results are saved directly to `Product` using `Link.save_result_products`.

This is too risky for the current budget and infrastructure because parsing can consume CPU, memory, network, and browser resources on the same machine that serves public pages.

The cheaper direction is to keep configuration and published data on the main server, but run parser workers from trusted local machines such as the project owner's laptop and another household laptop.

## Assumptions

- Admin users can define apple-related parser sources in the main Django admin.
- A local worker can authenticate to the server with a dedicated token or narrow service credential.
- Local workers can periodically pull active parser source configs from the server.
- Local workers can parse remote shop/product pages locally and send normalized results back to the server.
- The main server validates and upserts parsed results before making them public.
- Multiple local workers may run at the same time, so the server must avoid duplicate work and duplicate product rows.
- Prices older than 30 days should not be displayed on listing/search/category blocks, but the product can remain visible without a current price.

## Proposed Approach

### Phase 1A: Make Production Parsing Safe

- Add a setting such as `ENABLE_IN_PROCESS_COMPANY_PARSING=False` for production.
- Hide or disable the existing Django admin parser action unless the setting explicitly allows it.
- Keep parser configuration editing in admin.
- Treat the production site as a config and result-sync API, not a parser runtime.

### Phase 1B: Category-Based Parser Sources

Introduce explicit parser source ownership around category and commercial experiment scope.

Possible model evolution:

- Keep `Link` as the first parser source model to avoid unnecessary new tables.
- Add fields only as needed:
  - source type or parser mode, for example static HTML or browser-rendered page;
  - parser config version/hash;
  - priority;
  - crawl interval;
  - lock/lease fields for distributed workers;
  - last success and last error metadata;
  - optional experiment label such as `apples-phase-1`.

Admin should support:

- filtering parser sources by category, company, active state, and experiment label;
- editing parser config JSON;
- testing or previewing parsing only in a safe local/dev path, not production browser execution;
- seeing last crawl status, worker name, product count, and last error.

### Phase 1C: Local Worker Sync

Add a small trusted worker flow:

1. Local worker authenticates to the main server.
2. Worker pulls a batch of active parser sources, filtered by category/experiment.
3. Server leases each source for a short time so another laptop does not parse the same source simultaneously.
4. Worker parses the source locally.
5. Worker posts normalized results back to the server.
6. Server validates the payload and upserts products and price history.
7. Server marks the source success/failure and releases the lease.

Suggested API shape:

- `GET /api/parser/sources/?category=apples&limit=...`
- `POST /api/parser/sources/{id}/lease/`
- `POST /api/parser/sources/{id}/results/`
- `POST /api/parser/sources/{id}/failure/`

The initial API can be admin/service-token only. Human SSO is useful later for a full knowledge-engine UI, but worker machines should use narrow credentials that can be revoked.

### Phase 1D: Parsed Product Upsert

Parsed result payload should include stable matching data:

- source id;
- source URL;
- product name;
- product URL if available;
- normalized category id or slug;
- company id;
- description if available;
- price, min price, max price, and currency;
- parsed timestamp;
- raw source fields useful for debugging.

Upsert strategy:

- Prefer matching by `source_id + product_url` when product URL exists.
- Fall back to `source_id + normalized product name`.
- Keep product rows stable so public pages and history are not recreated every sync.
- Mark products inactive only after repeated absence or explicit source result, not after one failed parse.

### Phase 1E: Price Freshness And History

Add explicit price freshness so old prices do not mislead users.

Recommended model behavior:

- `Product.price` remains the latest accepted price for simple existing templates.
- Add `Product.price_updated_at` or equivalent freshness timestamp.
- Add `ProductPriceHistory` with:
  - product;
  - source link;
  - price/min/max price;
  - currency;
  - observed_at;
  - raw value or raw text;
  - worker/source metadata if useful.

Display rules:

- Listing/category/search blocks show price only when `price_updated_at` is within 30 days.
- Product/company detail pages can show the product even when price is stale, but should not present stale price as current.
- Admin can see the latest price, freshness, and history.
- Later, public pages may show a price trend if this becomes useful and legally/business-wise appropriate.

### Phase 1F: Multiple Local Machines

Multiple laptops can participate without a paid queue if the server owns leases.

Lease requirements:

- worker registers a name or machine id;
- worker requests work in small batches;
- server sets `leased_by` and `leased_until`;
- expired leases can be picked up by another worker;
- result posts must include the lease token or lease id;
- server rejects stale/invalid result submissions.

Operational defaults:

- one browser per laptop at first;
- small batches, for example 5-20 sources;
- per-domain delay and timeout;
- clear logs on the local worker;
- no parsing while the user is actively relying on the laptop for heavy work.

## Risks And Unknowns

- Parser configs are brittle and will need visible failure reporting.
- Product deduplication can create duplicates if source URLs are missing or names vary.
- Server-side result validation is important because worker laptops are less controlled than a server.
- Worker credentials must be narrow, revocable, and excluded from git.
- Some sites may block local IPs or change output by region/browser state.
- Price display needs careful wording so stale or parsed prices do not create trust/legal problems.
- The first apple scope needs concrete categories, source shops, and matching rules.

## Test Strategy

- Model tests for product price freshness and price history creation.
- API tests for auth, source listing, lease creation, lease expiry, result submission, and invalid/stale lease rejection.
- Upsert tests for repeated result submission, changed price, missing product URL, and failed parse.
- Admin tests or smoke checks for parser source fields and disabled production parsing action.
- Template tests for hiding prices older than 30 days on listing surfaces.
- Local worker dry run against saved HTML fixtures before live parsing.

## Documentation Updates

- Update `docs/business/domains/companies-and-shops/README.md` with price freshness and history rules.
- Add implementation result notes after the first apple parser sync is working.
- If the API contract stabilizes, add an engineering note for local parser worker setup and credential handling.

## Implementation Checklist

- [ ] Confirm apple category/source scope and first source list.
- [ ] Disable or guard in-process production parser execution.
- [ ] Add parser source fields needed for category-based local sync.
- [ ] Add service-token authentication for local parser workers.
- [ ] Add parser source list/lease/result/failure endpoints.
- [ ] Add price freshness and price history storage.
- [ ] Update public price display rules for stale prices.
- [ ] Build a local worker command or script that pulls configs and submits results.
- [ ] Add tests for leases, upserts, price history, and stale price hiding.
- [ ] Document local worker setup and first apple workflow.
