# Distributed Product Parser Workers

Trusted parser workers can run outside the AgroMega web host. They communicate only through the token-authenticated `/api/parser/` contract; public pages never depend on a worker being online.

`parser_studio/` is the separately installed local desktop control surface in the parent `am-dev` workspace. It uses the same API contract and never connects directly to the Django database.

## Ownership And Compatibility

- `am-core` owns parser source configuration, leases, accepted product state, price history, and parser-attempt audit records.
- A worker owns fetching/rendering a remote source and extracting a normalized result batch.
- Apples are the first dataset, not a special parser mode. Category and experiment filters select work without changing the shared contract.
- Existing global XPath maps remain supported. New and repaired sources should prefer item-scoped maps.
- Existing worker payloads remain valid. New lifecycle behavior is opt-in through `snapshot_complete`.

## Worker Credential

Create a dedicated active service user per machine, grant only `companies.use_parser_worker_api`, and create a DRF token. Keep the token outside git and pass it through `PARSER_WORKER_TOKEN` or `--token`. Revoking the token or permission stops that machine without affecting other workers.

Parser Studio stores tokens through the operating-system keyring. Grant `companies.run_parser_source_on_demand` only to trusted interactive operators who may run a source before its normal crawl interval. This permission does not bypass an active lease or an inactive source.

## Control And Catalog API

The scheduled worker contract remains backward compatible: `GET /api/parser/sources/` returns only due sources by default. Interactive tools may use:

- `GET /api/parser/sources/?scope=all` for the bounded source catalog;
- `GET /api/parser/sources/<id>/` for source configuration and runtime state;
- `GET /api/parser/companies/` and `GET /api/parser/categories/` for filter metadata;
- `GET /api/parser/attempts/?source=<id>` for run audit history;
- `GET /api/parser/products/?source=<id>` for accepted products;
- `GET /api/parser/price-history/?source=<id>` for observations;
- `POST /api/parser/sources/<id>/lease/` with `force=true` for authorized on-demand execution.

Catalog, product, attempt, and history endpoints are read-only and bounded. The server remains authoritative for every lease and accepted state transition.

## Parser Map

Preferred item-scoped configuration:

```json
{
  "item": "//article[contains(@class, 'offer')]",
  "name": ".//h2/text()",
  "price": ".//*[contains(@class, 'price')]/text()",
  "link": ".//a/@href",
  "snapshot_complete": true
}
```

`item` is the product container XPath. Other selectors are evaluated relative to each container. `snapshot_complete` should be `true` only when the worker result covers every offer represented by the source, including all required pages or scrolling.

Legacy maps without `item` still evaluate global field lists. If non-empty field lists return different counts, the worker stops and records a failure instead of risking incorrect product/price pairing.

## Running On Another Machine

The machine needs the compatible AgroMega code/runtime, network access to the main site and source websites, and Firefox/geckodriver only for browser-rendered sources.

```bash
./manage.py run_local_parser_worker \
  --base-url https://agromega.example/ \
  --token "$PARSER_WORKER_TOKEN" \
  --category apples \
  --experiment apples-phase-1 \
  --limit 5
```

The base URL must include the public path root and be reachable from the worker. The flow is:

1. List due sources with token authentication.
2. Lease one source using a server-issued lease token.
3. Fetch and parse the source locally.
4. Submit normalized products through HTTP.
5. Retry uncertain result submissions with the same lease token; the server returns the recorded successful receipt without duplicating products or price history.
6. Treat a server-rejected result as a known failure and submit that failure with the same lease token.
7. Retry uncertain failure submissions with the same lease token; the server returns the recorded failure receipt without duplicating audit attempts.

## Safety Limits

The server bounds products per result, raw diagnostic bytes per product, future timestamp tolerance, complete-snapshot shrinkage, and consecutive complete-snapshot misses before deactivation. Environment settings:

- `PARSER_MAX_PRODUCTS_PER_RESULT` (default `500`)
- `PARSER_MAX_RAW_PRODUCT_BYTES` (default `16384`)
- `PARSER_MAX_CONFIG_BYTES` (default `65536`)
- `PARSER_MAX_FUTURE_OBSERVATION_MINUTES` (default `5`)
- `PARSER_MISSING_DEACTIVATION_THRESHOLD` (default `3`)
- `PARSER_MIN_COMPLETE_SNAPSHOT_RATIO` (default `0.5`)
- `PARSER_WORKER_SUBMIT_RETRIES` on the worker (default `2`)

Every accepted price observation retains its raw diagnostic data within the configured bound. The latest public price advances only when the observation is at least as recent as the current accepted price.

A complete snapshot is rejected when it is empty or contains fewer products than the configured ratio of the source's currently active products. Rejection does not age or deactivate products. The bundled worker records the rejection as a parser failure so it is visible in source status and attempt history. Temporarily lower the ratio only for a verified, intentional catalog reduction.

## Verification

Before enabling a new source:

- run the worker with `--dry-run` against saved or controlled HTML;
- confirm product identity, relative URLs, decimal-comma prices, and optional fields;
- confirm whether the source is truly a complete snapshot;
- run one HTTP submission and inspect `Product`, `ProductPriceHistory`, `ParserSourceAttempt`, and the source lease/status fields in Django admin;
- repeat the same result request with the same lease token when testing idempotent recovery.
