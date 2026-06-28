# Plan: Organic Search Phase 1

- Date: 2026-06-28
- Status: Draft
- Owner: TBD
- Related domain: Catalog Information, Advertising Marketplace, Companies And Shops, Events Calendar, Classification And Taxonomy
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`
- Related investigation: `docs/work/results/2026-06-28-organic-search-product-investigation.md`

## Goal

Create the first implementation slice for organic-search growth: improve how existing public pages describe themselves to search engines and users, define which page types should be indexable, and prepare the first content-backed category commercial landing pages.

The outcome should help existing clients by making adverts, company profiles, products, and events more discoverable, while giving new visitors useful search landing pages that connect reference information with practical next actions.

## Non-Goals

- Do not build the full category + location page matrix in Phase 1.
- Do not generate large numbers of landing pages without content and indexation rules.
- Do not replace the cookie consent model or bypass analytics/advertising consent.
- Do not redesign the whole site navigation.
- Do not introduce a new CMS or external SEO dependency.
- Do not expose private diary data or user-only profile data.

## Current Understanding

AgroMega already exposes a wide public surface:

- category and catalog pages from `core.posts` and `core.classifier`;
- advert list/detail pages from `core.adverts`;
- company list/detail pages and product offers from `core.companies`;
- event list/detail pages from `core.events`;
- news pages from `core.news`;
- a plant diary landing page;
- sitemap views for main pages, adverts, and news.

Current gaps identified in the investigation:

- company pages need page-specific metadata and schema;
- advert pages need commercial structured data and better indexation lifecycle rules;
- event pages need Event structured data;
- breadcrumb structured data should be consistent across category/detail pages;
- category/filter URLs need a clear index/canonical/noindex policy;
- category commercial landing pages need curated content before broad rollout.

## Assumptions

- Search Console data may not be immediately available. If it is not available, Phase 1 starts with a manually curated category set.
- Existing `Category.meta` is the preferred place for category title, description, H1, and intro copy where possible.
- Current `Advert.active_objects` remains the public active advert source for SEO-visible advert modules.
- Expired adverts should not become permanent high-priority SEO pages without an explicit product decision.
- Structured data should be generated only from visible public page content.
- Content additions should be Ukrainian-first and written for humans, not keyword stuffing.

## Proposed Approach

### 1. Define Page Indexation Policy

Add a compact technical policy in docs and enforce it in templates/views where needed.

Initial rules:

- Index:
  - homepage;
  - active top-level and second-level category pages with meaningful metadata/content;
  - published catalog post detail pages;
  - active advert detail pages;
  - company list/detail pages where companies are active;
  - active/upcoming event list/detail pages;
  - curated category commercial landing pages.
- Canonical or noindex:
  - paginated list pages when appropriate;
  - thin filter URLs;
  - internal search result pages;
  - empty category landing pages;
  - private/profile pages;
  - expired advert pages until an expiry strategy is decided.

Implementation candidates:

- Add template blocks/helpers for `robots` and canonical metadata.
- Review `templates/base.html`, category templates, advert templates, company templates, event templates, and search templates.
- Keep the sitemap aligned with the policy.

### 2. Add Structured Data Foundation

Add JSON-LD where the existing public data is sufficient:

- `BreadcrumbList` for category, post detail, advert detail, company detail, and event detail pages.
- `Product` or `Offer` for advert details where price/contact/category/location are visible.
- `Organization` or `LocalBusiness` for company details.
- `Product` or `Offer` fragments for company products where product data is visible and useful.
- `Event` for event details.

Implementation candidates:

- Prefer small template includes under existing app template folders, for example:
  - `core/adverts/templates/adverts/includes/structured_data.html`
  - `core/companies/templates/companies/includes/structured_data.html`
  - `core/events/templates/events/includes/structured_data.html`
  - shared breadcrumb include if it can stay simple.
- Escape JSON safely and avoid invalid JSON when optional fields are absent.
- Add tests that assert required JSON-LD keys appear on representative pages.

### 3. Improve Metadata Coverage

Add page-specific title, description, Open Graph, and canonical coverage:

- Company list/detail pages:
  - title and meta description;
  - Open Graph title/description/url/image where logo exists;
  - canonical URL.
- Event list/detail pages:
  - stronger list description;
  - canonical URL;
  - Open Graph image where poster exists.
- Advert pages:
  - keep existing title/description;
  - add canonical URL for detail;
  - review list pagination robots/canonical behavior.
- Category pages:
  - preserve existing `Category.meta` behavior;
  - add fallback copy that is useful and not duplicated across every category.

### 4. Create Category Commercial Landing MVP

Build the first landing page pattern without creating a large page matrix.

Initial behavior:

- Use selected active categories.
- Show category intro from `Category.meta`.
- Show related catalog posts.
- Show active adverts in the category.
- Show companies/products in the category.
- Include clear actions:
  - add advert;
  - view all adverts in category;
  - view company/product offer;
  - read related catalog guide.
- Noindex the page if it has insufficient content.

Possible URL shape:

- Reuse existing category pages when the category already has the right public URL and can be enhanced safely.
- If a separate commercial page is cleaner, use a clear path such as `/categories/<slug>/market/`.

Decision needed before implementation:

- Whether Phase 1 enhances existing category pages directly or creates a separate commercial landing route.

Recommended default:

- Enhance existing second-level category pages first, because they already have metadata, sitemaps, breadcrumbs, and catalog context.

### 5. App/Admin Data Additions

Add minimal app fields only if needed for the MVP. Prefer existing fields first.

Candidate additions:

- `Company`:
  - optional `contact_phone`;
  - optional `contact_email`;
  - optional `service_area_text`;
  - optional `is_verified`;
  - optional `meta_description` if `description` is not enough.
- `Product`:
  - optional `updated` timestamp or freshness display if prices/offers are maintained.
- `Advert`:
  - optional `advert_type` choices: buy, sell, service, rent, exchange.
  - This can wait if the MVP can use category/title/description without type.
- `Category` or related metadata:
  - avoid new SEO fields until `MetaData` is confirmed insufficient.

Recommended Phase 1 stance:

- Do not add database fields unless the page cannot be made useful with existing data.
- If new fields are added, create migrations, admin updates, and focused tests in the same implementation.

### 6. Content Changes And Additions

Content work is required for Phase 1. The app can render landing pages, but search performance depends on useful category and company copy.

Initial content tasks:

- Choose 5-6 MVP categories:
  - Рослинництво
  - Садівництво
  - Тваринництво
  - Птахівництво
  - Препарати
  - Техніка
- For each selected category, add or improve:
  - title;
  - meta description;
  - H1;
  - 2-4 sentence intro;
  - short buyer/seller guidance;
  - links to relevant catalog subcategories or posts.
- For active companies, improve:
  - concise description;
  - location and service area;
  - product/category association where known;
  - logo where available;
  - website/contact accuracy.
- For active adverts, improve moderation/content guidance:
  - title format;
  - category required/recommended;
  - location recommended;
  - price clarity;
  - photo guidance.
- For events, encourage:
  - clear title;
  - start/stop dates;
  - location/address;
  - organizer details;
  - poster image;
  - registration URL if available.

Content governance:

- Add a short editor checklist under `docs/business/domains/` or `docs/engineering/` after implementation confirms the exact fields and workflow.
- Keep Ukrainian copy natural and useful; do not create near-duplicate pages with only keyword swaps.

## Risks And Unknowns

- Search Console data may change category priorities.
- Some categories may have too little advert/company/product data to justify indexable commercial modules.
- Structured data can become invalid if optional fields are rendered carelessly.
- Expired advert handling needs a product decision; `HttpResponseGone` for invalid pagination exists, but expired detail lifecycle should be confirmed.
- Company data may be stale or incomplete, which can reduce trust if surfaced more aggressively.
- Enhancing existing category pages may affect catalog UX; separate landing URLs may reduce risk but add more routes to maintain.

## Test Strategy

Use focused Django tests plus manual page checks.

Automated tests:

- Company list/detail metadata renders expected title/description/canonical/OG values.
- Company detail structured data renders valid JSON-LD for a company with and without logo/products.
- Advert detail structured data renders valid JSON-LD for active adverts with price/location/photo.
- Event detail structured data renders valid JSON-LD for an upcoming event.
- Category pages keep canonical/noindex behavior for querystring/filter URLs.
- Sitemap output matches indexation policy for affected page types.
- Category commercial MVP page/module handles:
  - category with posts/adverts/companies;
  - category with only posts;
  - category with too little content and noindex behavior.

Manual verification:

- Open representative pages locally:
  - homepage;
  - selected category page;
  - advert detail;
  - company detail;
  - event detail.
- Validate generated JSON-LD with a structured-data parser or Google Rich Results Test after deployment.
- Check rendered titles/descriptions in page source.
- Confirm no third-party analytics/advertising scripts load before consent.

Suggested commands:

```bash
just test-target core.adverts
just test-target core.companies
just test-target core.events
just test-target core.posts
just check
just flake
```

## Documentation Updates

During or after implementation:

- Update `docs/work/results/` with implementation and verification summary.
- Update domain notes if new business rules are confirmed:
  - `docs/business/domains/advertising-marketplace/README.md`
  - `docs/business/domains/companies-and-shops/README.md`
  - `docs/business/domains/catalog-information/README.md`
  - `docs/business/domains/events-calendar/README.md`
  - `docs/business/domains/classification-and-taxonomy/README.md`
- Add a durable SEO/content checklist if the workflow becomes repeatable.
- Write a decision record only if a long-lived routing/indexation decision is made, such as separate commercial landing URLs versus enhancing existing category URLs.

## Implementation Checklist

- [ ] Confirm whether Search Console data is available before category selection.
- [ ] Decide whether category commercial MVP enhances existing category pages or uses separate URLs.
- [ ] Confirm first 5-6 MVP categories.
- [ ] Define reusable robots/canonical approach.
- [ ] Add metadata coverage for company, advert, event, and selected category pages.
- [ ] Add structured data includes and tests.
- [ ] Add category commercial modules for selected categories.
- [ ] Add noindex/canonical behavior for thin or querystring pages.
- [ ] Prepare category copy and client-facing content guidance.
- [ ] Improve selected company/profile/ad/event content records.
- [ ] Run targeted tests and checks.
- [ ] Record implementation result and update domain docs with confirmed rules.
