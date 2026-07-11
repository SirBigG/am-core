# Advert Sitemap Retention Result

- Date: 2026-07-11
- Plan: `docs/work/plans/2026-07-11-advert-sitemap-retention.md`

## Delivered

- Added `ADVERT_SITEMAP_RETENTION_DAYS`, defaulting to 90 days.
- The advert sitemap now retains active records for `ADVERT_ACTIVE_DAYS + ADVERT_SITEMAP_RETENTION_DAYS` after their latest update.
- Manually deactivated and deleted adverts remain excluded.
- Public advert-list freshness is unchanged and still uses `Advert.active_objects`.

With current defaults, adverts appear in listings for 30 days and remain in the sitemap for up to 120 days from their latest update.

## Verification

- `AdvertSitemapTests`: 3 tests passed.
- `just flake`: passed.
