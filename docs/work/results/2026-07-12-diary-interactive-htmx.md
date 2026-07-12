# Result: Interactive Asynchronous Diary With HTMX

- Date: 2026-07-12
- Plan: `docs/work/plans/2026-07-12-diary-interactive-htmx.md`
- Status: Implemented and verified

## Delivered

- Added HTMX 2.0.10 to the existing frontend npm workspace and webpack build. The build emits a local `htmx.min.js`; no new CDN dependency was introduced.
- Added HTMX request detection and a small `HX-Trigger` response convention to diary views.
- Made add-action modal submissions asynchronous while preserving normal multipart Django form POSTs and redirects as the no-JavaScript fallback.
- Invalid asynchronous add-action submissions return the bound server-rendered modal form with preserved values and validation errors.
- Made quick watering asynchronous on diary list/detail, including server-side validation, duplicate-submit protection, loading state, accessible success/error announcements, and ordinary redirect fallback.
- Refreshes the coherent diary list or detail workspace after success so dashboard counts, timeline/card history, last-action state, attention state, and recommendations remain consistent.
- Added a small Fetch-based compatibility path when HTMX is unavailable or blocked; it uses the same form attributes, headers, response triggers, and server-rendered fragments.
- Allowed native mobile Flatpickr behavior instead of forcing the desktop calendar and added localized Today/Yesterday shortcuts.
- Added idempotent initialization for swapped forms, date controls, and existing diary interactions.
- Added 44px minimum date-shortcut targets and accessible live status presentation.

## Tests Added

- Successful HTMX add-action returns a 204 response with a refresh event and writes exactly one item.
- Invalid HTMX add-action returns the bound modal fragment, preserves text, displays Django validation, and performs no write.
- Successful HTMX quick watering returns a refresh event and writes exactly one watering item.
- Missing quick-watering selection returns an error event and performs no write.
- Multipart HTMX add-action saves a valid photo upload.
- HTMX add-action without a CSRF token is rejected with no write.

Existing ordinary POST/redirect, ownership, safe-next-url, form, recommendation, image, plant lifecycle, and diary rendering coverage remains in the targeted diary suite.

## Verification

- `just test-target core.diary` — PASS, 130 tests.
- Targeted `flake8 core/diary/views.py core/diary/tests.py` in the `core` container — PASS.
- `npm run build:static` — PASS; existing Sass/Bootstrap deprecation warnings remain.
- `just collectstatic` — PASS.
- `git diff --check` — PASS.
- In-app browser at 390x844 — PASS:
  - no horizontal page overflow;
  - Today/Yesterday controls present;
  - diary action field renders with the native-compatible `date` input contract;
  - quick-watering save completed without URL navigation;
  - success status was announced;
  - modal reset to `aria-hidden=true`;
  - submission from the second detail-page opener restored focus to that exact `quick-panel-add-action` control after replacement;
  - diary action count, latest action, weekly count, watering date, and attention summary refreshed immediately.

Repository-wide `just flake` still reports pre-existing E122 failures in gitignored `content_refresh_runs/*/scripts/refresh_post.py` files. The files changed by this work pass targeted lint.

## Decisions And Follow-ups

- The first slice refreshes one coherent workspace region per page instead of maintaining many out-of-band fragments. This reduces stale derived state and keeps the initial interaction contract understandable.
- No database migration, API change, domain-rule change, or forum change was required.
- Native iOS Safari and physical Android device verification was not available in this environment and remains a release-device check.
- Entry edit/delete, plant lifecycle actions, and filter history remain later slices from the accepted plan.
- If HTMX is adopted outside the diary, create a project-wide engineering decision and extract the request/response convention into shared infrastructure.
