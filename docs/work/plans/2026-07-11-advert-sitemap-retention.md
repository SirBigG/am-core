# Plan: Advert Sitemap Retention

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: Advertising marketplace
- Related decisions: SEO baseline and organic search phase 1

## Goal

Keep recently expired advert detail URLs discoverable in the advert sitemap for a bounded period instead of removing them on the first day they leave the active listing.

## Non-Goals

- Showing expired adverts in the active advert list.
- Retaining manually deactivated or deleted adverts in the sitemap.
- Changing advert detail-page availability.

## Current Understanding

`Advert.active_objects` includes active adverts updated within `ADVERT_ACTIVE_DAYS` (30 days by default), and the sitemap currently uses that same manager. Detail pages remain available after expiry.

## Proposed Approach

- Add `ADVERT_SITEMAP_RETENTION_DAYS`, defaulting to 90 days after active expiry.
- Select sitemap adverts with `is_active=True` and an update date within active days plus retention days.
- Cover active, retained-expired, too-old, and manually deactivated cases with tests.

## Test Strategy

- Run focused advert sitemap tests.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add tests.
- [x] Implement retention.
- [x] Run verification.
- [x] Record result.
