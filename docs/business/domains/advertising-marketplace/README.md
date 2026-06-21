# Domain: Advertising Marketplace

## Purpose

Advertising marketplace lets AgroMega clients create items about buying or selling something. It supports client-created commercial listings.

## Actors

- Clients who create buying or selling items.
- Users who browse or respond to those items.
- Administrators or moderators who may review, edit, hide, or remove items.

## Core Workflows

- A client creates an item for buying or selling something.
- Users discover marketplace items.
- The item may be updated, closed, hidden, or removed.

## Business Rules

- Items are created by clients.
- Items are about buying or selling something.
- Marketplace content is separate from stable catalog information.
- Public adverts are subject to baseline site terms, publication/moderation rules, and advert-specific rules seeded as flatpages.
- The advert author is responsible for truthfulness, legality, accuracy, and current availability of the advertised item or service.
- Contact details included in public adverts may be visible to other users and should be treated as intentionally published data.

## States And Lifecycle

The confirmed lifecycle is still unknown. Likely states to clarify include draft, active, expired, closed, hidden, rejected, or deleted.

## Neighboring Domains

- Classification and taxonomy, if marketplace items are categorized.
- Companies and shops, if items are connected to a company or seller profile.
- Authentication and identity, because client ownership matters.

## Implementation Map

- Django app: `core/adverts`.

## Open Questions

- What item types exist: buy, sell, service, rent, exchange, or others?
- Do items require moderation before publication?
- Do items expire automatically?
- How do users contact the client?
- Are there pricing, location, image, or category requirements?
- Who is the final legal owner/contact for privacy and marketplace complaints?
