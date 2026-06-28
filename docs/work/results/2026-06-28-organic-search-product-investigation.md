# Result: Organic Search Product Investigation

- Date: 2026-06-28
- Status: Draft product investigation
- Scope: Current `am-core` public features, organic-search growth opportunities, and product extensions that help existing AgroMega clients while attracting new visitors.

## Executive Summary

AgroMega already has the raw material for an organic-search product loop: reference catalog content, a shared taxonomy, advert listings, company profiles, product links, events, news, plant diary, and internal cross-links. The strongest near-term opportunity is not to publish generic blog posts. It is to turn the existing taxonomy and client-generated commercial data into durable, indexable landing pages that answer concrete Ukrainian agricultural search intents.

Recommended first bet: build category-led commercial and reference landing pages that connect:

- catalog knowledge: varieties, breeds, diseases, preparations, equipment categories;
- live supply/demand: AgroMega adverts;
- companies and shops: sellers, service providers, product offers;
- practical next action: add advert, contact company, create diary, read guide.

This helps existing clients by making their adverts, company profiles, and product offers more discoverable from search, while creating useful pages for new visitors who are searching by crop, product, region, problem, or buying intent.

## Current Public Surface

Observed from local routes, templates, models, domain notes, and a live homepage fetch.

### Strong Existing Assets

- Homepage links to major sections and recent public content.
- Category tree exists in `core.classifier` with active/inactive state, hierarchy, images, and optional `MetaData`.
- Catalog/post pages exist under category URLs such as `/<parent>/<child>/<slug>-<id>.html`.
- Category pages already support title, meta description, H1, intro text, breadcrumbs, and country/attribute filters.
- Post detail pages already emit Article JSON-LD and social metadata.
- Adverts have public list/detail pages, active expiry, category, location, price, contact, photos, views, and sitemap.
- Companies have public list/detail pages with type, location, website, products, prices, and product-to-post links.
- Events have public list/detail pages with dates, location, poster, and sitemap inclusion.
- News pages are exposed, but rely on an external API.
- Plant diary has a public landing page and private user workflows.
- Sitemaps include main URLs, category URLs, posts, events, adverts, and news.

### Current SEO Gaps

- Company pages lack custom meta description, Open Graph metadata, canonical tags, and Organization/LocalBusiness/Product structured data.
- Advert pages have basic metadata, but no Product/Offer/LocalBusiness structured data and no indexable category/location landing pages.
- Event pages have good visible event fields but no Event structured data.
- Category filter URLs are canonicalized to the unfiltered page, so useful long-tail combinations are not intentionally indexable.
- Search results pages create internal search statistics but should not be treated as a primary SEO landing-page strategy.
- News pages appear more like aggregation/outbound linking than owned editorial depth.
- Plant diary is a good acquisition feature, but it is only one landing page instead of a cluster of plant-care intent pages.
- The taxonomy can create many pages, but there is not yet a product rule for which pages deserve indexation versus noindex/canonical.

## Market Pattern Notes

Competitor scan was lightweight and directional, not a full keyword-volume study.

- AgroPortal positions as a news/media hub with strong title/meta copy, multilingual alternates, NewsMediaOrganization structured data, and editorial categories. Source: https://agroportal.ua/
- Tripoli.land positions as a transactional agricultural directory: grain prices, traders, farmers, companies, elevators, ports, logistics, tariffs, and many specific indexable directory pages. Source: https://tripoli.land/ua
- SuperAgronom blocked direct fetch with 403 during this investigation, but the market category is clear: agronomist knowledge hubs compete for crop, disease, technology, and practical farm-management queries. Source checked: https://superagronom.com/
- Google Search Central emphasizes unique, useful page titles/descriptions, crawlable links, sitemaps, structured data where appropriate, and content made for users. Source: https://developers.google.com/search/docs/fundamentals/seo-starter-guide

The strategic opening for AgroMega is the intersection competitors do not fully own: reference content plus live marketplace/company actions. A visitor should be able to search a crop or category, learn what it is, see active offers, find suppliers, and continue into a diary or client contact workflow.

## Organic Search Opportunity Map

### 1. Category Commercial Landing Pages

Intent examples:

- `купити насіння томату україна`
- `продам пшеницю україна`
- `добрива для огірків купити`
- `сільгосптехніка оголошення україна`
- `саджанці яблуні купити`

Product shape:

- One SEO landing page per high-value active category.
- Page combines category intro, active adverts, companies/products, related catalog guides, and add-advert CTA.
- Index only curated categories with enough content.
- Keep low-value empty pages noindex or excluded.

Why this fits:

- `Advert.category`, `Advert.location`, `Advert.price`, `Company.products`, `Product.category`, and `Category.meta` already exist.
- The existing advert and company data can become a client-value engine, not just isolated listings.

Priority: P0.

### 2. Category + Location Pages

Intent examples:

- `купити кукурудзу львівська область`
- `агро компанії вінниця`
- `насіння соняшнику київська область`

Product shape:

- Curated pages for category plus region/location where there is enough supply.
- Show active adverts, companies, and a concise local intro.
- Add canonical/indexation rules to prevent thin page explosion.

Why this fits:

- `Advert.location`, `Company.location`, and classifier location models already exist.
- Useful for clients because it surfaces them to users with purchase/location intent.

Priority: P1 after category pages.

### 3. Company And Product SEO Upgrade

Intent examples:

- company name searches;
- `магазин насіння [місто]`;
- `купити [product] [company]`;
- `агро послуги [місто]`.

Product shape:

- Upgrade company detail pages with metadata, Organization/LocalBusiness schema, product sections, verified/status labels, contact clarity, and links to relevant category landing pages.
- Add optional client-managed profile fields: service area, contact channels, official description, delivery/payment notes, product categories.
- Add product freshness date where prices/offers are parsed or maintained.

Why this fits:

- Existing `Company`, `Product`, `Link`, parser-map, price, category, post relationship, and website fields already support the data model.

Priority: P0/P1.

### 4. Reference Content Hubs From Existing Catalog

Intent examples:

- `сорти цибулі`
- `хвороби яблуні`
- `породи голубів`
- `характеристики сорту яблуні`

Product shape:

- Improve parent/child category pages as real guides, not only lists.
- Use category attribute filters as human-readable comparison controls.
- Add “related offers” and “companies selling/supporting this category” blocks.
- Create evergreen “best/compare/choose” pages only where data supports them.

Why this fits:

- Category metadata, post structured attributes, registry variety data, related posts, products-for-post, and existing catalog URLs are already in place.

Priority: P0 for top categories, P1 broader rollout.

### 5. Plant Diary Acquisition Cluster

Intent examples:

- `щоденник рослин онлайн`
- `календар поливу помідорів`
- `догляд за огірками теплиця`
- `коли підживлювати базилік`

Product shape:

- Keep the current plant diary landing page.
- Add public plant-care landing pages for selected crops that lead to diary creation.
- Use private `CategoryAIProfile` knowledge as internal/editorial source material, but publish only reviewed public content.
- Add diary templates: tomato greenhouse, basil windowsill, cucumber bed, orchard season.

Why this fits:

- The diary domain already has categories, plants, actions, photos, harvest units, and AI profile context.

Priority: P1 because it needs editorial/product care, but it can become a strong top-of-funnel feature.

### 6. Event Pages With Rich Results Potential

Intent examples:

- `агро виставка україна 2026`
- `аграрні події київ`
- `семінар фермерів україна`

Product shape:

- Add Event structured data.
- Add event type and location landing pages.
- Preserve completed events as useful archives when they have unique content; otherwise reduce crawl priority.
- Encourage organizers to add speaker, organizer, registration URL, and agenda fields.

Why this fits:

- Event model already has title, type, location, address, start/stop, poster, and text.

Priority: P1.

### 7. News As Support, Not Main SEO Bet

Intent examples:

- current market/news queries.

Product shape:

- Keep news for freshness and engagement.
- Prefer owned explainers, category hubs, and client/company pages for durable search value.
- If news remains API-backed/outbound-heavy, avoid making it the center of organic strategy.

Priority: P2.

## Recommended Roadmap

### Phase 1: Technical And Product SEO Foundation

1. Add a page-indexation policy:
   - index: curated categories, rich company pages, active advert detail pages, rich event pages, selected category/location pages;
   - noindex or canonical: pagination, thin filters, empty landing pages, private/profile pages, weak search result pages.
2. Add structured data:
   - Product/Offer for adverts where data is sufficient;
   - Organization/LocalBusiness for companies;
   - Event for event detail pages;
   - BreadcrumbList for category/post/detail pages.
3. Add metadata coverage:
   - company list/detail;
   - advert category pages once built;
   - event list/detail;
   - category/location pages.
4. Add Search Console export workflow:
   - current top queries;
   - pages with impressions but low CTR;
   - pages ranking positions 8-20;
   - non-indexed pages and sitemap errors.

### Phase 2: Category Commercial Landing MVP

Build a reusable `CategoryLandingView` or extend existing category views for selected categories.

Each page should include:

- H1 and intro from `Category.meta`;
- active adverts in the category;
- companies/products in the category;
- related catalog posts;
- “add advert” and “claim/update company” calls to action;
- noindex when content thresholds are not met.

Initial category candidates should come from current Search Console data and active site inventory. If Search Console data is unavailable, start with categories already visible in footer/homepage:

- Рослинництво
- Садівництво
- Тваринництво
- Птахівництво
- Препарати
- Техніка

### Phase 3: Client Visibility Features

1. Company profile upgrade:
   - profile completeness score;
   - verified/contact status;
   - product categories;
   - service area;
   - freshness date for offers.
2. Advert upgrade:
   - advert type: buy/sell/service/rent;
   - contact method fields;
   - structured location fields;
   - optional expiration/renewal reminders.
3. Client dashboard:
   - views from internal counter;
   - clicks to contact/website;
   - “appears on these category pages” visibility.

### Phase 4: Plant Diary And Reference Content Loop

1. Choose 5-10 crops with clear search demand and available internal knowledge.
2. Create public plant-care pages linked to diary templates.
3. Add diary onboarding from each page.
4. Link diary pages back to catalog guides and relevant marketplace/company offers.

## Prioritized Backlog

| Priority | Initiative | Client Value | New Visitor Value | Effort | Notes |
| --- | --- | --- | --- | --- | --- |
| P0 | Category commercial landing MVP | High | High | Medium | Best intersection of existing data and search intent. |
| P0 | Company SEO metadata/schema upgrade | High | Medium | Low-Medium | Directly helps existing clients be discovered. |
| P0 | Structured data for adverts/events/companies | Medium | Medium | Low-Medium | Supports richer interpretation and quality. |
| P0 | Search Console data review | High | High | Low | Needed before final category prioritization. |
| P1 | Category + location pages | High | High | Medium | Must avoid thin page explosion. |
| P1 | Product/offer freshness and profile completeness | High | Medium | Medium | Helps trust and client retention. |
| P1 | Plant diary crop landing pages | Medium | High | Medium | Strong acquisition if editorial quality is good. |
| P1 | Event structured data and location/type pages | Medium | Medium | Low-Medium | Good for event organizers and seasonal traffic. |
| P2 | News/editorial refresh strategy | Low-Medium | Medium | Medium | Less durable than reference/commercial pages. |

## Metrics To Track

- Organic sessions by page type: category, post detail, advert detail, company detail, event detail, plant diary.
- Search Console impressions, clicks, CTR, and average position by page type.
- Indexed pages by sitemap section.
- Advert submissions from organic landing pages.
- Company profile visits and outbound website/contact clicks.
- Diary signups from plant-care pages.
- Internal search phrases from `SearchStatistic`.
- Pages with organic impressions but missing client action blocks.

## Risks And Guardrails

- Do not generate thousands of thin category/filter/location pages. Index only pages with enough useful content and clear search intent.
- Do not expose private diary data. Public plant-care pages should use reviewed generic knowledge, not user journals.
- Do not turn every advert into permanent SEO content after expiry. Expired adverts should use a clear lifecycle: gone, archived with no contact, or redirected to a category landing page.
- Do not make third-party analytics/ad scripts bypass consent. Organic strategy should work with the current privacy-safe consent layer.
- Keep Ukrainian language quality high. Many opportunities depend on natural Ukrainian search phrasing, not translated keyword stuffing.

## Suggested Next Step

Create an implementation plan for Phase 1 and the Category Commercial Landing MVP. Before coding, pull Search Console data if available; otherwise start with a small manually curated set of 5-6 categories and validate the pattern.

Candidate plan file:

- `docs/work/plans/2026-06-28-category-commercial-landing-mvp.md`

## Evidence

Local files reviewed:

- `settings/urls.py`
- `core/posts/views.py`
- `core/posts/models.py`
- `core/posts/templates/posts/detail.html`
- `core/posts/templates/posts/list_order.html`
- `core/classifier/models.py`
- `core/adverts/models.py`
- `core/adverts/views.py`
- `core/adverts/templates/adverts/list.html`
- `core/adverts/templates/adverts/detail.html`
- `core/companies/models.py`
- `core/companies/views.py`
- `core/companies/templates/companies/list.html`
- `core/companies/templates/companies/detail.html`
- `core/events/models.py`
- `core/events/views.py`
- `core/events/templates/events/list.html`
- `core/events/templates/events/detail.html`
- `core/news/views.py`
- `core/news/templates/news/list.html`
- `core/news/templates/news/detail.html`
- `docs/business/domains/*`

External sources checked:

- AgroMega live homepage: https://agromega.in.ua/
- AgroPortal homepage: https://agroportal.ua/
- Tripoli.land Ukrainian homepage: https://tripoli.land/ua
- SuperAgronom homepage fetch attempt: https://superagronom.com/
- Google Search Central SEO Starter Guide: https://developers.google.com/search/docs/fundamentals/seo-starter-guide
