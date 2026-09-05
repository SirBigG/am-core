# Domain: Companies And Shops

## Purpose

Companies and shops represents organizations shown in AgroMega, including company profiles, shops, addresses, product information, prices, and other important business details.

## Actors

- Users who browse company or shop information.
- Company representatives or clients who may provide or maintain profile details.
- Administrators or content managers who verify, edit, or moderate company data.

## Core Workflows

- Create and maintain company or shop profiles.
- Publish important business information such as addresses, products, and prices.
- Let users discover company, shop, product, or pricing information.

## Business Rules

- Company and shop records can contain important contact, location, product, and pricing data.
- Company records may include optional exact latitude/longitude coordinates for map-based shop cards, "where to buy" views, and future variety availability/spread visualizations. These coordinates are more precise than the shared city/area `Location`.
- Accuracy matters because users may rely on this information for business decisions.
- Company data may connect to product/catalog data and commercial listings.
- Public company submissions are subject to baseline site terms and publication/moderation rules seeded as flatpages.
- Company representatives or content submitters are responsible for having authority to publish company contact, location, product, and pricing data.
- Product prices have freshness semantics. Listing, category, search, and related-product blocks should only present prices as current when the latest accepted price observation is within the configured freshness window, currently 30 days.
- Product and company detail pages may keep showing the product after the price becomes stale, but stale prices should not be presented as current.
- Parsed product prices should keep observation history so admins can audit when a worker saw a price and from which parser source.
- Parser ingestion is category-agnostic. Apples may be used as the first operational dataset, but shared company, source, product, price, geography, and API rules must work for every existing site and category without category-specific branches in the core models.
- Parser workers may run on any trusted machine that can reach the authenticated API and the source websites. The server remains authoritative for source leases, accepted results, current public state, and audit history.
- Interactive parser tools are separate API clients, not part of the production web process. They may inspect company/source/product/history projections and request an on-demand run with an explicit permission, but they never write directly to the application database or bypass active leases.
- Existing parser configurations and worker payloads remain supported. Item-scoped XPath extraction is opt-in and should be preferred for new or repaired sources because it keeps optional fields attached to the correct product container.
- A price observation is always retained when valid, but an older observation must not replace a newer current price. Observations too far in the future are rejected.
- Product absence affects public availability only when a worker explicitly marks a successful result as a complete source snapshot. Partial or legacy results do not age missing products. A product is deactivated only after the configured number of consecutive complete-snapshot misses and is reactivated when seen again.
- Empty complete snapshots and snapshots below the configured safe ratio of the source's active catalog are rejected before product state changes. This protects public availability when a shop changes its HTML or a parser selector stops matching.
- Successful result submission is idempotent for the source lease token so a worker can safely retry after losing the HTTP response.
- Failure submission is also idempotent for the source lease token so a worker can retry an uncertain failure receipt without duplicating audit attempts.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include draft, published, verified, hidden, suspended, or archived.

## Neighboring Domains

- Catalog information, if companies list or reference products.
- Advertising marketplace, if adverts are connected to companies or shops.
- Classification and taxonomy, if companies or products are categorized.
- Authentication and identity, if company representatives manage profiles.

## Implementation Map

- Django app: `core/companies`.

## Open Questions

- Who owns and edits company data?
- Is there a verification process?
- What public wording should be used for stale parsed prices beyond the first simple "needs update" message?
- Which parser sources can truthfully claim complete snapshots, especially when a shop uses pagination or infinite scrolling?
- Are shops separate entities from companies, or a type of company profile?
- Which fields are required for a public company or shop listing?
- Who is the final legal owner/contact for privacy and company data complaints?

## Product-to-catalog matching and review

Matching is category-scoped and only considers published posts. A single full
normalized name match can create an automatic link. Whole-phrase matches inside seller titles and unique distinctive-token matches
may populate a link with review status. Explicit parenthetical/pipe-separated
catalog aliases are considered; longer full phrases outrank base names, and tied
candidates remain unlinked. Bundles remain unlinked. Arbitrary substrings and full-text article rank never
create links. Name equality is a deterministic rule, not a claim of 100% semantic
certainty. Missing catalog entries are normal and do not block product ingestion.

Products carry a matching status and explanation. Existing records enter the
review queue without losing their current links: historical manual decisions
cannot be distinguished from automatic ones. Administrators filter Products by
matching status and category; the source-link filter is removed from this page.
They can choose a post or clear a wrong link, which confirms the decision, or use
the confirmation action/status to approve an existing link or no link at all.
Confirmed decisions survive imports and the backfill command, even when the
catalog later gains a similarly named post. Django admin history records edits
and confirmations. To retry an intentionally unlinked product, change its status
back to review and save.

Automatic links are reassessed when the persisted name or category changes.
Bundles, multi-graft plants, cultivar sports and partial matches need human review;
this release does not implement an alias dictionary or an entity model for them.
Migration 0014 adds the queue fields only; it neither merges duplicate offers nor
bulk replaces historical links. Deploy code and run migrations before using the
new admin fields. Parser payloads remain compatible.

Validation (2026-09-05): 77 companies/parser API tests and scoped pre-commit
checks passed. Local migration applied; migration consistency check passed.
The broader 535-test core/API run had 9 failures and 5 errors in other areas
(canonical request rendering, host expectations, Silk query counts and news
cache behavior); it is not a clean full-suite result. No production deployment
or historical link rewrite was performed. A read-only evaluation of 80 BioСад
preview rows against the local catalog proposed 27 links; this is coverage,
not an accuracy measurement or a production-catalog estimate.

### Admin-managed matching dictionary

`Словник зіставлення товарів` in the companies admin owns the matching vocabulary.
Each record stores one normalized unique word, its purpose (ignored scoring token
or bundle/multi-variety marker), and an active flag. Bundle markers optionally
match word prefixes to cover endings; ignored tokens match whole words only.
The dictionary currently applies to all categories. Administrators can add,
edit, disable or delete rules using standard Django permissions and audit history.

Active rules are read from the database on each matching assessment, with no
process cache or hardcoded fallback vocabulary. Changes affect subsequent
assessments; they do not bulk rewrite existing product links or override confirmed
manual decisions. Full-name equality retains priority over dictionary rules;
ignored words only affect token scoring, not normalized full-name equality.
The `+` delimiter remains a structural multi-item check in code.

Migration 0015 creates the dictionary and 0016 seeds the previous vocabulary
once to preserve existing behavior. The seed is historical initial data, not a
runtime default: disabled or deleted entries are not recreated on application
startup. Reversing only the seed migration leaves operator-owned rules intact.
Deploy with migrations before serving requests using the new matcher.
