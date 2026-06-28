# Result: Cookie Consent

- Date: 2026-06-21
- Plan: docs/work/plans/2026-06-21-cookie-consent.md
- Status: Implemented

## Summary

Added a first-party cookie consent layer in `templates/base.html`.

Google Analytics and Google AdSense are no longer rendered as initial third-party script tags. When analytics or adverts are enabled, the page renders a cookie banner with accept all, reject optional, and customize controls. The user choice is stored under a versioned localStorage key and can be reopened from the footer through "Налаштування cookies".

Analytics consent controls loading `gtag.js`. Advertising consent controls loading the Google AdSense script.

Follow-up release note: `ENABLE_ADVERTS` controls Google AdSense/advertising consent only. AgroMega's own marketplace advert blocks are controlled separately by `ENABLE_INTERNAL_ADVERTS`, which stays enabled by default in local dev while AdSense is disabled.

## Files Changed

- `templates/base.html`
- `templates/footer.html`
- `core/utils/tests/test_feature_flags.py`

## Verification

- `just test-target core.utils.tests.test_feature_flags` passed.
- `just check` passed with existing warnings for CKEditor 4 support and non-unique `User.email`.
- `just flake` passed.

## Follow-Up

- Configure Google AdSense Privacy & messaging or another Google-certified CMP for EEA, UK, and Switzerland traffic. This first-party banner is not an IAB TCF certified CMP by itself.
- Decide whether rejected advertising consent should request non-personalized/limited ads instead of no AdSense script.
- Consider moving the inline consent script to a static JS file before tightening CSP from report-only to enforcement.
