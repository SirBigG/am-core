# Result: Admin Index Metrics

- Date: 2026-06-28
- Plan: `docs/work/plans/2026-06-28-admin-index-metrics.md`

## Summary

The Django admin index now shows a permission-aware operational summary for the last 30 days.

Metrics shown when the staff user has view permission:

- Adverts created in the period, with active-created count in the card description.
- Posts published in the period, using `Post.publish_date` because `Post` does not have a creation timestamp.
- Users joined in the period, using `User.date_joined`.
- Latest feedback created in the period, shown as recent descriptive entries with title, email, text preview, timestamp, and admin links.

The index keeps Django admin's app list and recent actions layout. Styling uses admin CSS variables so it works with the existing light/dark admin theme.

Follow-up review cleanup moved the template tag into the admin-specific `admin_extras` library and caches the metrics on the request, so the content and sidebar blocks reuse the same dashboard data during one admin index render.

## Verification

- `./manage.py test core.utils.tests.test_admin_dashboard --settings=settings.test_settings`: passed.
- `./manage.py test core.utils.tests.test_admin_theme --settings=settings.test_settings`: passed.
- `uv tool run djlint --profile=django --lint templates/admin/index.html`: passed.
- `./manage.py collectstatic --noinput -i node_modules --settings=settings.dev`: passed, copying the new dashboard stylesheet.
- `./manage.py check --settings=settings.test_settings`: passed; existing CKEditor 4 and non-unique `User.email` warnings remain.

## Follow-Up

- If "new posts" should mean authoring date rather than publish date, add a real `created` field to `Post` and migrate this metric.
