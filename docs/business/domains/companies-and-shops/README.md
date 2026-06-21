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
- Accuracy matters because users may rely on this information for business decisions.
- Company data may connect to product/catalog data and commercial listings.
- Public company submissions are subject to baseline site terms and publication/moderation rules seeded as flatpages.
- Company representatives or content submitters are responsible for having authority to publish company contact, location, product, and pricing data.

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
- How are product prices maintained and dated?
- Are shops separate entities from companies, or a type of company profile?
- Which fields are required for a public company or shop listing?
- Who is the final legal owner/contact for privacy and company data complaints?
