# Reusable category hubs

Editor and agent workflow:
[Managing category pages, Crop Hubs and Guide Hubs](../../business/guides/category-pages-and-widgets.md).

Latest release verification and resolved deletion-permission issue:
[Hub deletion permissions](../security/2026-10-17-hub-deletion-permissions.md)
(646/646 tests on a fresh test database; full application lint passes).

Date: 2026-10-17. Implemented locally; no production deployment or catalog migration performed.

## Ownership and configuration

`core/posts/crop_hub.py` builds server-rendered context from admin-managed configuration. `CategoryHub` points one-to-one to an existing `Category`; ordered `CategoryHubSection` rows reference existing categories through explicit foreign keys. There is no category dictionary in application settings and no crop-specific list to maintain in code. No article/category copies, new dependency, service or duplicated crop template are required. Existing Category and Post ownership, slugs, stored canonical URLs and article bodies remain unchanged. The local review setup adds a crop-level landing category and composes legacy content through references.

Configuration workflow:

1. Open **Classifier → Category hubs** (`/admin/classifier/categoryhub/`) and add a hub for an existing category. A hub can also be added through the **Category hub** inline on that category's edit page; follow its change link to configure sections.
2. Enter an optional introduction and select **Active** when ready. Hubs default to inactive. Active hub configuration takes precedence over that category's ordinary catalog/Guide Hub presentation; disabling it restores the prior presentation.
3. Add section rows, selecting existing categories with autocomplete. Choose the semantic role: varieties, diseases, pests, growing and care, or additional section. Set labels/descriptions, sort order and active state as needed. Each primary role occurs at most once; multiple additional sections are supported. A target category may occur only once per hub.
4. Optionally select an existing guide-source category (including a separate taxonomy branch), and a site/language display restriction. Blank guide source uses guide placements directly on the hub category. Blank site/language applies wherever this database owns content. Existing category meta title and H1 are retained.

Model/admin validation rejects recursive section references to the hub itself or its ancestors, including forged POSTs and new unsaved parent forms. Explicit catalog/guide references may cross taxonomy branches; this composes existing content without moving it. Duplicate primary roles are rejected by formset validation before writes and by a database constraint. Runtime queries independently check current public ancestry and non-recursive reference relationships, so later taxonomy moves or withdrawals cannot broaden marketplace scope. Standard Django permissions control hub creation/editing and section configuration separately; category-edit access alone does not grant hub-edit access.

The single database remains the content boundary. Optional site/language restrictions control hub display, not Post ownership or translation. A future shared-database Sites rollout needs explicit content memberships. One hub record per category is supported; per-site translated configuration variants are outside this implementation.

Migration `classifier.0016_admin_category_hubs` creates only the two configuration tables, with no category seeding or transformation. It was applied to the local development database. New hubs can be added for potatoes, apples or any other existing category entirely through admin.

## Knowledge and growing sequence

Public articles require `status=True`, a non-future publication date, a saved canonical URL, and active category ancestry at every depth. Counts use distinct Post identities across the configured category subtree. Page reads never generate or save missing article URLs.

Growing steps reuse `GuideSection` and `GuideSectionArticle`, ordered by existing sort order and primary key. Configure placements on the hub category, or select **Guide category** in admin to reuse an existing public guide category. Recommended editorial sequence: preparation and seed selection; planting; care; nutrition and irrigation; protection; harvest and storage. These headings and their article placements are editorial configuration, not inferred from article titles. Empty steps are omitted. Articles placed in more than one step appear only in their first eligible placement on this landing page.

Featured varieties use title/primary-key order and are labelled as an alphabetical selection. Images and characteristics are optional and are not synthesized. Additional articles exclude the configured catalog subtrees and articles already placed in guides or featured cards. A configured growing category supplies the additional-content browse link.

## Marketplace eligibility and reconciliation

Hub metrics and the new `hub=<existing-hub-slug>` marketplace/company filters call the same `crop_market_offers()` query. Invalid or unavailable hub scopes return 404 instead of silently showing all offers. Category and region filters further narrow the hub scope. Scope survives category redirects, marketplace tabs, forms, pagination, variety links and variety-page category navigation. Catalog articles within a configured variety subtree also link to that strict scope.

Eligibility requires:

- Existing `market_offers()` checks: active Product and Company, public Post/category, matching Product category and owning Post category, and a positive exact price or positive minimum price when exact price is absent.
- A configured **variety** subtree, with complete active ancestry and a published article with saved URL. Disease/pest and unrelated category products are not eligible crop identities.
- `match_status` of `auto` or `confirmed`, plus exact case-insensitive trimmed equality between seller product name and catalog title. A reviewed broad title mention still fails this conservative gate.
- A price timestamp within the smaller of `CROP_HUB_FRESH_DAYS` and `PRODUCT_PRICE_FRESH_DAYS`, excluding future timestamps. Hub freshness defaults to 30 days.
- One observation per Company/Post pair, selecting the newest eligible price timestamp and then highest primary key. Metrics therefore count **unique seller/cultivar offers**, not every SKU, package or duplicated crawler row.

One SQL aggregate computes deduplicated offer count, distinct companies, distinct catalog identities, and latest price-observation date. Featured offer links use one bounded membership query rather than one query per card. Sellers include any active company with an eligible offer; the existing unscoped company directory retains its shop-only convention.

The hub labels these as observations on AgroMega, never national coverage, producers, or verified planting/food supplies. The only supported group is catalog-variety offers. Planting material, food products, crop protection and fertilizer groups are deliberately not inferred without explicit product-purpose relationships.

### Mapper limitations

The upstream matcher can associate a cultivar mentioned in a broader product name and stores less certain matches as `review`. Old rows and manually confirmed associations do not contain independently verified product-purpose data. The hub excludes broad matches even if confirmed, so names with seed/packaging descriptors may be excluded despite being valid products. Case/trim equality is deliberately stricter than the upstream punctuation/alias normalizer. This loses recall to protect aggregate precision; it is not an upstream data repair.

Unscoped marketplace pages retain their existing behavior and may still contain broad historical associations, including the reported Bellarosa contamination. No crawler, match rule, alias, or existing Product relationship was rewritten. Reliable broader eligibility needs reviewed product-purpose classification and identity provenance, rather than a blacklist of a few chemical words.

## Prices

Product currently has total/range prices and currency, but **no verified package mass, quantity, measurement unit or planting/food classification**. The implementation always returns an unavailable price summary and displays “Недостатньо порівнюваних пропозицій” with the precise reason. It never divides a package price based on title text or mixes package totals into a crop price.

The context carries currency, unavailable unit, zero **comparable** observation/seller counts, date/method availability, and configurable quality-gate metadata (`CROP_HUB_PRICE_MIN_OFFERS=5`, `CROP_HUB_PRICE_MIN_SELLERS=3`). There is no enabled median calculation: those thresholds alone cannot validate prices without measurement provenance. A future normalized-observation source should separate planting and food groups, then calculate a median of seller-level medians after deduplication and freshness checks. That source/schema decision remains outside this implementation.

## Caching and SEO

The existing Django cache stores plain context under a hash of database name, configured site ID, public origin, locale, category primary key, database configuration snapshot and freshness/threshold settings. Configuration is freshly loaded in two bounded queries (hub and ordered sections); changes to activation, role targets, ordering, labels, introduction, guide source and site/language restrictions change or bypass the cached result immediately. A warm aggregate context performs no additional aggregate/content queries. `CROP_HUB_CACHE_TTL` defaults to 300 seconds and is capped at 300. No queryset/model instances are cached. Current development settings intentionally use DummyCache; deployed settings use the existing LocMemCache, with independent caches in each worker.

Updates, removals and expiry may take up to five minutes to reach a cached hub, while linked listings read current eligibility. No signal invalidation is promised for bulk updates. For an immediate withdrawal, clear each application's cache/restart its workers. The hub's own category and ancestry are validated on every request, including cache hits. Future stricter withdrawal requirements should move to shared versioned invalidation or revalidate cached public identities, without silently relying on process-local signals.

Only stored category canonical paths render hubs; alternate matching routes redirect permanently to that stored path, and wrong parents return 404. Canonical, breadcrumbs, existing CollectionPage markup, one H1 and crawlable links are retained. Filtered marketplace/company destinations are noindex. There are no new sitemap URLs or filter combinations added to sitemaps.

## Local inventory and acceptance limits

The initial local inventory had 147 categories, 3,270 Posts and 3,035 Products. It **does not have the `kartoplya` category or its three supplied production child slugs**. The initial nested demo configuration was at the wrong level and has been corrected as described below; a production-equivalent content inventory cannot be claimed. The corrected local review setup explicitly creates a crop-level `kartoplya` category under the same plant root as Коренеплідні, retaining the older catalogs in place; it does not claim production inventory parity.

The actual local potato variety catalog is `/koreneplidni/sorty-kartopli/`:

| Observation | Local value |
| --- | ---: |
| Eligible public variety articles | 120 |
| Raw potato Product records | 195 |
| Product records with `match_status=review` | 195 |
| Strict eligible offers | 0 |
| Sellers with strict eligible offers | 0 |
| Varieties with strict eligible offers | 0 |
| Comparable price observations | 0 |

The production-equivalent disease/pest categories remain unavailable locally; no zero production counts are claimed. The crop-level potato hub references the existing demo Guide Hub as its guide source, reusing three visible guide steps containing ten eligible articles. Its original four sections and eleven placements remain intact, including the hidden section. No latest eligible market observation date or aggregate price exists locally.

The original read-only apple preview showed 81 public varieties, 2 disease articles and zero strict offers/sellers/market varieties. Current automated tests create separate potato and apple hub records and section references without settings overrides, proving the database-backed reuse path. Warm service reads now require two configuration SELECTs; aggregates remain cached, and cold query cost stays constant as offers grow.

## Verification and navigation

Requested potato URLs are covered with isolated PostgreSQL test fixtures, including `/kartoplya/`, `/kartoplya/kartoplia-sorty/`, `/kartoplya/hvoroby-kartopli/`, `/agromarket/?hub=kartoplya`, `/companies/?hub=kartoplya`, existing variety article paths, and strict `/agromarket/variety/<post-id>/?hub=kartoplya`. A configured but absent pest section is omitted. Separate apple fixtures prove reuse. Tests cover descendants, hidden ancestors, drafts, future publication dates, guide duplicates, stale/future/invalid prices, review matches, chemical/packaging title contamination, distinct sellers, repeated listings, filters, canonical redirects, no-market rendering, incomplete configuration, cache scope and query bounds.

Browser QA verified the real saved potato hub in Chrome at desktop size and 390 × 844. It has one H1 and document/scroll width of 390, with wrapping actions and no horizontal overflow. The original read-only apple preview also exercised reuse. This does not establish production-data parity or live provider availability.

Validation commands (from the integration workspace):

```bash
docker compose exec -T core python manage.py test api.v1.content core.posts.tests core.classifier.tests core.companies --settings=settings.test_settings --keepdb --noinput
docker compose exec -T core flake8 core/posts/crop_hub.py core/posts/tests/test_crop_hub.py core/posts/views.py core/companies/market.py core/companies/market_views.py core/companies/views.py
docker compose exec -T core python manage.py makemigrations --check --dry-run
docker compose exec -T core npm --prefix frontend run build:static
```

Final API/configuration revision: **343 tests, 341 passed, 2 baseline failures** (17.080 seconds). The focused API/cache/migration run passed 26/26; the final API-only run passed 6/6. Tests cover both admin entry points, API CRUD and permissions, recursive targets, explicit cross-category catalogs/guides, duplicate roles, content preservation and immediate guide/cache changes. That earlier readback confirmed one explicitly saved hub and unchanged category/Post counts; the later level correction adds one main crop category, documented below.

The broad suite's two unrelated failures were reproduced by loading the original HEAD views in a separate process, without changing workspace files:

- `PublicationMetadataTests.test_canonical_uses_publication_url_even_on_an_alias_path`: expects 200 where the existing canonical redirect returns 301.
- `SiteMapTests.test_return_context`: expects four sitemap groups, receives five.

Python lint passes; migration drift check reports no ungenerated changes. The additive classifier migration was applied locally. Static build succeeds with existing Sass import deprecation warnings. Offline djlint was unavailable in the tool cache; template compilation/rendering is covered by Django tests. Existing CKEditor/email-uniqueness and naive-date warnings remain.

## Changed files and rollout

Implementation: `api/v1/content/hubs.py`, `api/v1/content/urls.py`, `core/posts/apps.py`, `core/posts/hub_invalidation.py`, `core/classifier/models.py`, `core/classifier/admin.py`, `core/posts/crop_hub.py`, `core/posts/views.py`, `core/companies/market.py`, `core/companies/market_views.py`, `core/companies/views.py`, and `settings/settings.py`.

Presentation: `core/posts/templates/posts/crop_hub.html`, company list/market list/market tabs/market variety templates, `frontend/src/scss/list.scss`, and its generated `core/posts/static/posts/list.css`.

Tests: `api/v1/content/tests/test_hubs.py`, `core/posts/tests/test_crop_hub.py` and `core/classifier/tests/test_category_hub_admin.py`. Migrations: `core/classifier/migrations/0016_admin_category_hubs.py` and the help-text-only `0017_explicit_hub_references.py`. Documentation: this record.

Before enabling against a target database, apply the additive migration, confirm category inventory and stored URLs, select hub/section categories in admin, configure actual growing-guide placements, inspect strict eligible records, build/collect static assets through the existing release workflow, and read back the category and scoped listings. No commit, push, production deployment, production write or infrastructure change was performed. The later local review configuration was explicitly requested and saved through local admin; see the follow-up below.


## Corrected local landing level and agent API

The Crop Hub belongs to the main crop category: `/kartoplya/`, at level 1 beside `/koreneplidni/`, rather than to a nested Guide Hub or variety catalog. The local database had an older taxonomy with no potato landing category. Through local admin, Category 2467 (`Картопля`, `kartoplya`) was added under plant root 71. Hub 1 was reassigned from the mistaken demo category to this category, and its guide source was explicitly set to category 2466. No CategoryHub remains attached to the nested demo. That demo retains `presentation_mode=guide_hub` and renders its original guide collection.

The source variety category 2327 remains at `/koreneplidni/sorty-kartopli/`; its existing 120 public varieties, article URLs, structured attributes and Product relationships remain intact. The hub's `varieties` reference connects this legacy branch to the new landing page. Guide source 2466 retains its four sections and eleven placements, exposing three visible sections and ten unique eligible articles. The hub composes these existing records without copying or moving them. Disease/pest catalog sections are absent locally and were not fabricated. The local database now has 148 Categories, 3,270 Posts and 3,035 Products.

All linked market surfaces use `hub=kartoplya`, deriving cultivar identity from that same variety-category reference. The existing 195 potato Product rows have `match_status=review`, so eligible offers, sellers and offered varieties are all zero. Prices remain unavailable because comparable measurement data is absent. Other legacy root-crop categories, such as carrot varieties, are outside the potato scope.

Review: `http://localhost:8000/kartoplya/`. Configuration: `/admin/classifier/categoryhub/1/change/`. API readback: `/api/content/hubs/?category=2467`, `/api/content/hub-sections/?hub=1`, and `/api/content/guide-sections/?category=2466`. Local IDs are evidence for this database, not defaults in code or data migrations. On production, configure the existing main potato category and its real source categories through admin/API.

The existing content API exposes permission-scoped hub, hub-section, guide-section and guide-placement CRUD plus category presentation GET/PATCH. See [Hub management API](../api/hub-management.md). The API can configure a crop-level hub and reuse categories anywhere in the existing tree. It does not create/reparent taxonomy categories or provision tokens.

The level-correction regression verifies root-level rendering with legacy sibling catalogs/guides, exclusions of unrelated root-crop articles and offers, matching marketplace and seller results, original article URLs, and independent nested Guide Hub rendering. The final crop/admin/API/company suite passes **112/112 tests** (3.411 seconds), including both new landing-level and market-navigation regressions. Python lint passes. A previously sequence-sensitive admin fixture now refreshes MPTT coordinates after another root insertion, so its URL assertion uses current tree state. Earlier broad verification remains recorded above. This correction required no schema migration. Marketplace/company pages now show the selected culture and a link back to its landing page; category choices stay within the configured variety scope, and reset/empty-state company links preserve `hub`. Browser QA confirmed the saved `/kartoplya/` page, the original standalone nested guide, scoped seller/category selectors, and return navigation. At 390 × 844 the corrected landing has one H1 and document/scroll widths of 390.
