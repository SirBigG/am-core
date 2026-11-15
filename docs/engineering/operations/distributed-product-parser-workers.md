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

Catalog reads are bounded. Product, attempt and history endpoints remain read-only.
The server remains authoritative for every lease and accepted state transition.

## Company And Source Management API

Trusted operators can maintain company profiles and parser configurations through
the same token-authenticated API, without a Django admin session:

| Resource | Collection | Detail | Methods |
| --- | --- | --- | --- |
| Companies/shops | `/api/parser/companies/` | `/api/parser/companies/<id>/` | GET/POST collection; GET/PUT/PATCH detail |
| Parser sources | `/api/parser/sources/` | `/api/parser/sources/<id>/` | GET/POST collection; GET/PUT/PATCH detail |

DELETE is unsupported (405). Use `active=false` to disable a record. These
companies belong to `core.companies`; `/api/registry/add-company/` imports
registration entities and does not maintain shop profiles.

All requests require `Authorization: Token <token>` and
`companies.use_parser_worker_api`. Additionally, POST requires
`companies.add_company` or `companies.add_link`, respectively; PUT/PATCH requires
`companies.change_company` or `companies.change_link`. Grant only the necessary
permissions to dedicated operator accounts. Existing worker tokens do not gain
write access. Permissions can be provisioned through the normal Django user/group
administration workflow; API writes themselves require no admin session.

Create a company with POST `/api/parser/companies/`:

```json
{
  "name": "Example nursery",
  "website": "https://shop.example.com/",
  "location_id": 123,
  "type": 1,
  "description": "Fruit tree nursery",
  "active": true,
  "parser_map": {"name": "//h2/text()", "price": "//span[@class='price']/text()"}
}
```

`name`, `website` and an existing `location_id` are required on creation (and
full PUT). Other writable fields are `slug`, `latitude` and `longitude`. Types:
1 shop, 2 service, 3 supermarket, 4 market. Slugs are generated when omitted;
provide a unique explicit slug if the generated one is already taken. Location
IDs can be found through `GET /api/locations/?loc=<prefix>`. Logo uploads are
outside this API. Read projections include geography labels and source counts.

Create a source with POST `/api/parser/sources/`:

```json
{
  "company_id": 123,
  "category_id": 456,
  "url": "https://shop.example.com/fruit-trees/",
  "source_type": "static",
  "parser_map": {
    "item": "//article",
    "name": ".//h2/text()",
    "price": ".//span[@class='price']/text()",
    "link": ".//a/@href",
    "snapshot_complete": false
  },
  "parser_config_version": "fruit-v1",
  "crawl_interval_minutes": 1440,
  "priority": 100,
  "active": false
}
```

`company_id`, `category_id` and `url` are required on creation/full PUT. Category
IDs are available through `GET /api/categories/`; the narrower
`/api/parser/categories/` catalog lists only categories already used by sources.
`source_type` accepts `static` or `browser`; `experiment_label` is also writable.
Create inactive sources while qualifying selectors, then PATCH `active=true` when
ready to schedule them. Creation does not fetch the URL or launch a parser.

PATCH only the fields being changed. A supplied `parser_map` replaces the entire
stored object; `null` or `{}` on a source restores company-default inheritance.
The response's `parser_map` retains its existing effective-configuration meaning;
`stored_parser_map` exposes the raw source override so clients can distinguish
inheritance. Company `parser_map` is always its stored default.

Configuration writes accept JSON objects or null, bounded by
`PARSER_MAX_CONFIG_BYTES`, with syntactically valid XPath selectors, supported
encoding names, boolean `snapshot_complete`, and integer `max_pages` in 1–50.
Empty objects may be saved before qualification. Validation does not establish
that selectors match the remote site or that a snapshot is complete; preview and
verify them in a compatible worker first. Catalog-only configurations may use a
valid selector matching no price nodes.

Unknown/read-only fields are rejected with 400. Runtime timestamps, leases,
crawl status and counts cannot be written through this interface. Source edits
return 409 while leased; changing a company default also returns 409 while any
of its sources is leased. Retry after the run completes or the lease expires.
Company/category reassignment returns 400 once a source has products or attempts;
create a new source instead to preserve historical ownership. No schema migration
is required. Deploy the backend before using these writes; existing Studio and
CLI clients continue to use their existing read/run contract. This API addition
does not add configuration-editing screens to Parser Studio.

Management writes record the operator, target and changed field names in Django
admin history in the same transaction as the mutation. Configuration values are
not copied into the history message. A database write conflict returns 409 with
no partial mutation. Company creation responses include `source_count=0`.

API creation, reassignment, configuration edits and worker writes lock the company
before the source; reassignment locks both companies in ID order. This prevents
new leases or newly attached sources from bypassing a concurrent company-default
edit. Work on different companies remains independent.

Workers can cache a source before leasing it. Results that explicitly submit a
`parser_config` different from the current effective map return 409 before product
or observation writes. Reload the source and rerun it; the existing lease can be
closed with a failure receipt. Successful result replays still return the original
receipt. Legacy clients omitting `parser_config` remain accepted and cannot receive
this stale-map check; prefer clients that submit the actual configuration snapshot.
The version label remains worker-supplied diagnostic metadata.

## Parser Map

Preferred item-scoped configuration:

```json
{
  "item": "//article[contains(@class, 'offer')]",
  "name": ".//h2/text()",
  "price": ".//*[contains(@class, 'price')]/text()",
  "link": ".//a/@href",
  "next_page": "//a[contains(@class, 'next')]/@href",
  "max_pages": 10,
  "snapshot_complete": true
}
```

`item` is the product container XPath. Other selectors are evaluated relative to each container. `snapshot_complete` should be `true` only when the worker result covers every offer represented by the source, including all required pages or scrolling.

`next_page` is an optional absolute XPath that returns the next page URL. Both Parser Studio and the bundled CLI worker follow it until it disappears. `max_pages` is a required operational safety bound when pagination is configured; it must be between 1 and 50, and reaching the bound while another page still exists fails the run rather than accepting an incomplete snapshot.

Legacy maps without `item` still evaluate global field lists. If non-empty field lists return different counts, the worker stops and records a failure instead of risking incorrect product/price pairing.

### Catalogs Without Prices And JSON Feeds

The result API accepts catalog entries with all price fields omitted or null. These
update product identity and last-seen state without creating price history or a
fresh market price. A catalog entry does not establish current stock availability.
In admin forms requiring a price XPath, `self::*[false()]` explicitly selects no
price. Keep `snapshot_complete=false` for a qualified subset.

Parser Studio additionally supports JSON object/array feeds using the same XPath
configuration: `/json/Products/item` selects entries in a `Products` array;
`./Title/text()` and `./Url/text()` read their title and URL. Object properties
become elements, arrays contain `item` elements, and null has no text. This is a
local Studio capability; older Studio versions and the bundled core CLI do not
support these JSON feed maps. Use the updated Studio runtime for such sources and
restart an already-open Studio process after updating its files. No core runtime
or API deployment is needed. Studio also honors HTML `base href` for product URLs
and pagination. The sibling `parser_studio/README.md` documents configuration.

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
