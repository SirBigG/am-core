# Plan: Knowledge Engine Product And Parser Integration

- Date: 2026-06-28
- Status: Draft
- Owner: TBD
- Related domain: Companies And Shops, Catalog Information, Classification And Taxonomy, Authentication And Identity
- Related plans:
  - `docs/work/plans/2026-06-28-organic-search-phase-1.md`
  - `docs/work/results/2026-06-28-organic-search-product-investigation.md`

## Goal

Move resource-heavy product parsing and product knowledge enrichment out of the main AgroMega Django site and into the separate AgroMega knowledge engine, while keeping `am-core` as the stable public SEO surface and local published index.

The main site should no longer run Selenium/browser parsers in-process. It should consume curated/synchronized product data from the knowledge engine and render public pages from local cached/read-model data so crawling, page rendering, and client workflows remain reliable on the current DigitalOcean deployment.

## Non-Goals

- Do not make public SEO pages depend on a live API call for every request.
- Do not remove current `Company` and `Product` data before a replacement sync is proven.
- Do not move user/session ownership out of `am-core`.
- Do not expose parser configuration or parser execution to unauthenticated users.
- Do not deploy the knowledge engine directly in this change; deployment should be a separate rollout step.
- Do not couple this to the forum project except by reusing the existing OIDC/SSO pattern.

## Current Understanding

`am-core` currently includes company/product parsing in the main Django app:

- `core.companies.parser` fetches remote pages with `requests` and can run Selenium/Firefox.
- `parse_many_links_with_same_browser` runs parser work from a Django admin action.
- `Link.parser_map` and `Company.parser_map` store XPath parser configuration.
- Parsed results write directly into `Product` rows.
- Product rows are used by company pages and product-for-post blocks.

This is risky on a small DigitalOcean app server because parsing can consume CPU, memory, network, file descriptors, browser processes, and request/admin worker time. A parser failure or slow external website can degrade the public site.

The existing forum integration already proves that `am-core` can act as an OpenID Connect provider:

- `oauth2_provider` is installed.
- `/o/` exposes OAuth/OIDC endpoints.
- `ensure_forum_oidc_application` creates/updates a client application.
- `social_oidc_begin` starts the forum authorization flow.
- `ForumOIDCValidator` customizes user claims.

## Assumptions

- The knowledge engine will become the owner of parser execution, parser configs, and product intelligence/enrichment.
- `am-core` remains the owner of public SEO URLs, template rendering, sitemaps, user sessions, and client-facing profile/dashboard pages.
- `am-core` can keep a local product read model for fast page rendering.
- The first integration can be pull-based or push-based; the safest initial approach is explicit sync into `am-core`.
- Knowledge engine deployment may start on a separate DigitalOcean droplet/app/container and can evolve later.

## Proposed Architecture

### Ownership Boundary

Knowledge engine owns:

- parser jobs and scheduling;
- Selenium/browser dependencies;
- parser configurations and source link definitions;
- product extraction, normalization, deduplication, enrichment, and matching;
- source freshness, crawl status, parser logs, and failure reasons;
- API endpoints for product read models and sync/export.

`am-core` owns:

- public company/category/advert/event/catalog pages;
- SEO metadata, canonical/noindex rules, sitemaps, and structured data;
- local published product index used by templates;
- client/company ownership and public profile workflows;
- authentication provider and SSO for related AgroMega services;
- fallback behavior when the knowledge engine is unavailable.

### Data Flow

Preferred first version:

1. Admin/editor manages parser sources and configs in the knowledge engine.
2. Knowledge engine runs parse jobs away from the main site.
3. Knowledge engine normalizes products and links them to source company/category/catalog identifiers where possible.
4. `am-core` periodically syncs a published product snapshot from the knowledge engine API.
5. `am-core` writes the snapshot into existing or new local read-model tables.
6. Public pages render from local data only.
7. If the knowledge engine is down, public pages keep rendering stale-but-known-good data.

Later options:

- Knowledge engine pushes webhooks to `am-core` after successful jobs.
- `am-core` requests targeted refreshes for a company/category.
- Client dashboard shows parser freshness and source status from cached sync metadata.

### Local Data Model Strategy

Conservative default:

- Keep `core.companies.Product` as the local public read model for Phase 1.
- Add external/source fields only when needed:
  - `external_id`
  - `source_service`
  - `source_url`
  - `synced_at`
  - `source_updated_at`
  - `sync_status`
- Keep `Company` in `am-core` for public profiles and SEO.
- Map knowledge-engine product/company/category references onto existing `Company`, `Product`, `Category`, and `Post` rows.

Alternative later:

- Introduce a separate `ProductIndexItem` read model if existing `Product` becomes too tied to legacy parser/admin behavior.

### Parser Migration Strategy

Phase A: Stop making parsing dangerous on the main site.

- Disable or hide the admin parser action in production.
- Add settings guard such as `ENABLE_IN_PROCESS_COMPANY_PARSING=False`.
- Keep manual HTML-file parsing only if needed and explicitly safe.
- Document that production parsing belongs to the knowledge engine.

Phase B: Move parser configs.

- Export current `Company.parser_map` and `Link.parser_map`.
- Import parser sources/configs into the knowledge engine.
- Keep read-only legacy parser config fields in `am-core` during transition.

Phase C: Sync product read model.

- Add a knowledge-engine API client in `am-core`.
- Add a management command such as `sync_knowledge_products`.
- Add idempotent upsert behavior.
- Track sync timestamps and source freshness.

Phase D: Retire legacy parser paths.

- Remove or fully disable Selenium/parser execution from `am-core`.
- Preserve only data rendering and sync logic.

## API Shape

Initial knowledge engine API should be boring and durable.

Suggested endpoints:

- `GET /api/products?updated_since=...`
- `GET /api/products/snapshot`
- `GET /api/companies/{external_id}/products`
- `GET /api/categories/{external_id}/products`
- `GET /api/parser-sources`
- `GET /api/jobs/{id}` for admin/status tooling

Suggested product payload:

```json
{
  "id": "knowledge-product-123",
  "name": "Насіння томату ...",
  "description": "...",
  "company": {
    "id": "knowledge-company-10",
    "name": "..."
  },
  "category": {
    "id": "knowledge-category-55",
    "slug": "..."
  },
  "catalog_post": {
    "id": 2779,
    "slug": "..."
  },
  "price": "120.00",
  "currency": "UAH",
  "url": "https://...",
  "is_active": true,
  "source_updated_at": "2026-06-28T12:00:00Z"
}
```

API requirements:

- authenticated service-to-service access;
- pagination or snapshot export;
- stable external IDs;
- explicit active/inactive state;
- timestamps for freshness;
- no parser execution from public unauthenticated endpoints.

## SSO And Auth

Reuse the forum pattern with a separate OIDC client for the knowledge engine.

Recommended additions in `am-core`:

- create a generic or dedicated command:
  - `ensure_oidc_application --client-id ... --redirect-uri ...`
  - or `ensure_knowledge_engine_oidc_application`;
- environment variables:
  - `KNOWLEDGE_ENGINE_BASE_URL`
  - `KNOWLEDGE_ENGINE_OIDC_CLIENT_ID`
  - `KNOWLEDGE_ENGINE_OIDC_CLIENT_SECRET`
  - `KNOWLEDGE_ENGINE_OIDC_REDIRECT_URI`
  - `KNOWLEDGE_ENGINE_OIDC_POST_LOGOUT_REDIRECT_URI`
- optional start URL similar to forum:
  - `/knowledge/login/` or `/social/login/knowledge-engine/`

SSO responsibilities:

- Human admin/editor login uses OIDC from `am-core`.
- Service-to-service sync should use a separate API token or OAuth client credentials style flow, not a browser session.
- Claims should include only what the knowledge engine needs: user id, email, display name, staff/admin flags if appropriate.

## DigitalOcean Deployment Shape

Recommended initial split:

- Main site:
  - existing `am-core` app/droplet/container;
  - public web requests only;
  - no Selenium/parser jobs.
- Knowledge engine:
  - separate DigitalOcean app/droplet/container;
  - worker process for parser jobs;
  - optional queue/Redis if jobs need scheduling/retry;
  - browser/Selenium dependencies isolated here.
- Database:
  - keep `am-core` database as public read/index database;
  - knowledge engine may have its own database for parser state, enrichment, and job logs.

The public site should survive knowledge engine downtime. A failed parse job should never take down AgroMega pages.

## Risks And Unknowns

- Data ownership needs a final decision: which service is authoritative for Company and Product?
- Category ID/slug mapping can drift between services.
- Product deduplication can create unexpected public page changes.
- Parser configs may contain brittle XPaths that need observability and review.
- SSO admin claims must not grant broad access accidentally.
- Running Selenium in the knowledge engine still needs resource limits and job timeouts.
- If product data is stale, SEO pages can mislead users; freshness should be visible.

## Test Strategy

`am-core` tests:

- OIDC application creation for knowledge engine client.
- API client handles success, pagination, auth errors, and service downtime.
- Sync command upserts products idempotently.
- Existing company/product pages render from synced local data.
- Product blocks continue rendering if last sync is stale.
- Production setting disables in-process parser action.

Knowledge engine tests, outside this repo:

- parser job isolation and timeout behavior;
- parser config validation;
- product normalization and stable IDs;
- OIDC login callback;
- API auth and pagination;
- export/snapshot contract.

Operational verification:

- Run a parser job without increasing main site CPU/memory.
- Simulate knowledge engine outage and confirm `am-core` pages still render.
- Confirm sync can be retried safely.
- Confirm parser failures are visible in knowledge engine admin/logs.

## Documentation Updates

- Update `docs/business/domains/companies-and-shops/README.md` with product data ownership and freshness rules after decisions are confirmed.
- Update `docs/business/domains/catalog-information/README.md` if knowledge engine becomes authoritative for product-to-catalog matching.
- Add an engineering decision if the service boundary is accepted.
- Write implementation result after the first sync/API integration lands.

## Implementation Checklist

- [ ] Decide whether knowledge engine is authoritative for products only, or for companies plus products.
- [ ] Decide local read model: keep `Product` or add `ProductIndexItem`.
- [ ] Disable or guard in-process production parsing in `am-core`.
- [ ] Export current parser configs and links.
- [ ] Define knowledge engine product API contract.
- [ ] Add knowledge engine OIDC client setup mirroring forum SSO.
- [ ] Add service-to-service API auth plan.
- [ ] Add `am-core` sync client and management command.
- [ ] Add idempotent product upsert and freshness metadata.
- [ ] Update company/category/product templates to show synced data safely.
- [ ] Add tests for OIDC setup, sync behavior, and parser guard.
- [ ] Deploy knowledge engine separately from main site.
- [ ] Run parser jobs in knowledge engine and verify main site stability.
