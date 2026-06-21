# Initial Domain Map

- Date: 2026-06-21
- Status: Draft

## Purpose

This note starts the business knowledge base for `am-core`. It records the first visible domain candidates from the current Django app structure so future feature work has a shared place to refine language, boundaries, and rules.

This is not a final DDD model. It is a map to improve through real work.

## Candidate Domains

### Advertising And Promotion

- Likely purpose: manage promotional or advertising content shown in the product.
- Implementation starting point: `core/adverts`.
- Open questions: Who buys or creates adverts? What targeting, approval, billing, or display rules exist?

### Analytics And Metrics

- Likely purpose: track product usage, content performance, or business metrics.
- Implementation starting point: `core/analytics`.
- Open questions: Which events are business-critical? Who consumes analytics? What privacy constraints apply?

### Classification And Taxonomy

- Likely purpose: organize content, companies, products, posts, or services into categories and terms.
- Implementation starting point: `core/classifier`.
- Open questions: Which taxonomies are controlled by admins, and which are user-generated? Are categories shared across domains?

### Companies And Products

- Likely purpose: represent agribusiness companies, company profiles, and products.
- Implementation starting point: `core/companies`.
- Open questions: What makes a company verified, active, hidden, or trusted? Who owns company profile data?

### Diary

- Likely purpose: support user or farm diary workflows.
- Implementation starting point: `core/diary`.
- Open questions: What business process does the diary support? Is it private user data, shared agronomy data, or both?

### Events

- Likely purpose: publish and manage agricultural events.
- Implementation starting point: `core/events`.
- Open questions: What event lifecycle exists? Are registrations, attendance, locations, or organizer roles part of the domain?

### News And Editorial Content

- Likely purpose: publish news or editorial material.
- Implementation starting point: `core/news`.
- Open questions: What editorial workflow exists? Are drafts, approvals, authors, tags, and publication windows modeled?

### Community Posts And Media

- Likely purpose: allow users to publish posts, attach media, and interact with community content.
- Implementation starting point: `core/posts`.
- Open questions: What moderation rules apply? What visibility, voting, comment, and media constraints exist?

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
