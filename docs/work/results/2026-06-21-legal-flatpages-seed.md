# Result: Legal Flatpages Seed

- Date: 2026-06-21
- Plan: docs/work/plans/2026-06-21-legal-flatpages-seed.md
- Status: Implemented

## Summary

Added Django data migrations that seed and refresh baseline AgroMega flatpages for About, Privacy Policy, Cookie Policy, Terms of Use, Publication and Moderation Rules, and Classified Ads Rules.

The initial seed is idempotent by flatpage URL. It creates missing pages and attaches them to existing Django Site records. A follow-up refresh migration updates these known legal page URLs in place so existing `about/` and `privacy_policy/` content receives the new baseline text too.

## Files Changed

- `core/services/migrations/0013_seed_legal_flatpages.py`
- `core/services/migrations/0014_refresh_legal_flatpage_content.py`
- `core/services/tests/test_legal_flatpages.py`
- `templates/footer.html`
- `docs/business/domains/advertising-marketplace/README.md`
- `docs/business/domains/companies-and-shops/README.md`
- `docs/business/domains/events-calendar/README.md`

## Verification

- `just test-target core.services` passed.
- `just check` passed with existing warnings for CKEditor 4 support and non-unique `User.email`.
- `just flake` passed.
- `just migrate services` applied `services.0014_refresh_legal_flatpage_content` to the local compose database.
- Direct shell check confirmed `/about/` and `/privacy_policy/` contain refreshed text.
- Removed embedded `<h1>` tags from seeded flatpage content because the flatpage template already renders `flatpage.title`; re-applied `services.0014_refresh_legal_flatpage_content` locally and confirmed all six legal flatpage bodies have no `<h1>`.

## Follow-Up

- Confirm the final legal owner/controller identity and privacy contact email.
- Implement a cookie consent banner or Google-certified CMP before loading non-essential analytics or advertising tags for jurisdictions that require consent.
- Update form flows with terms/privacy acknowledgement where appropriate.
