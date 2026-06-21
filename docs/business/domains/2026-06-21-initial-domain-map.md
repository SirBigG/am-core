# Initial Domain Map

- Date: 2026-06-21
- Status: Draft

## Purpose

This note starts the business knowledge base for `am-core`. It records the first visible domain candidates from the current Django app structure so future feature work has a shared place to refine language, boundaries, and rules.

This is not a final DDD model. It is a map to improve through real work.

## Candidate Domains

### Advertising And Promotion

- Confirmed purpose: support client-created items about buying or selling something.
- Implementation starting point: `core/adverts`.
- Current domain folder: `advertising-marketplace/`.
- Open questions: What item types, moderation, expiry, contact, pricing, location, and category rules exist?

### Analytics And Metrics

- Likely purpose: track product usage, content performance, or business metrics.
- Implementation starting point: `core/analytics`.
- Open questions: Which events are business-critical? Who consumes analytics? What privacy constraints apply?

### Classification And Taxonomy

- Confirmed purpose: provide a shared tree of categories used by other core project areas.
- Implementation starting point: `core/classifier`.
- Current domain folder: `classification-and-taxonomy/`.
- Open questions: Who can maintain the tree, and what happens when categories move or are removed?

### Companies And Products

- Confirmed purpose: represent companies, shops, addresses, product information, prices, and other important business details.
- Implementation starting point: `core/companies`.
- Current domain folder: `companies-and-shops/`.
- Open questions: Who owns company data, how verification works, and how product prices are maintained.

### Diary

- Confirmed purpose: support personalized user plant, field, diary, and journal workflows.
- Implementation starting point: `core/diary`.
- Current domain folder: `diary-and-journals/`.
- Open questions: What exact journal types exist, how private they are, and whether sharing exists.

### Events

- Confirmed purpose: provide a calendar of events that anyone can share with other people.
- Implementation starting point: `core/events`.
- Current domain folder: `events-calendar/`.
- Open questions: What event lifecycle exists, whether moderation is required, and whether registrations or attendance are tracked.

### News And Editorial Content

- Likely purpose: publish news or editorial material.
- Implementation starting point: `core/news`.
- Open questions: What editorial workflow exists? Are drafts, approvals, authors, tags, and publication windows modeled?

### Catalog Information

- Confirmed purpose: provide the main catalog information area, including varieties, diseases, and similar reference content.
- Implementation starting point: `core/posts`.
- Current domain folder: `catalog-information/`.
- Open questions: Which catalog entity types exist, who maintains them, and how much legacy social post behavior remains.

### Authentication And Identity

- Likely purpose: authenticate users and integrate with identity providers or forum SSO.
- Implementation starting point: `core/pro_auth`.
- Open questions: Which identity flows are primary? What user states matter to the business?

### Registry And Reference Data

- Likely purpose: manage reference data used by other domains.
- Implementation starting point: `core/registry`.
- Open questions: Which data is authoritative, who maintains it, and what downstream workflows depend on it?

### Services And Reviews

- Likely purpose: expose services and collect or display user reviews.
- Implementation starting point: `core/services`.
- Open questions: Who provides services? What review rules, anti-abuse constraints, and service lifecycle states exist?

## Cross-Domain Questions

- Which domains own user-generated content versus admin-managed content?
- Which domains require moderation or approval?
- Which domains expose public pages, API endpoints, or both?
- Which domains share taxonomy, media, search, or permissions?
- Which workflows cross from `am-core` into the sibling forum project?

## Next Steps

Create focused domain notes as each area is touched. Start with the language used by product stakeholders and users, then connect that language back to the implementation.
