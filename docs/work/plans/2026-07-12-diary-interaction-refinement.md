# Plan: Diary Interaction Refinement And Local Frontend Assets

- Date: 2026-07-12
- Status: Accepted from user feedback
- Owner: TBD
- Related domain: Diary And Journals
- Related plan: `docs/work/plans/2026-07-12-diary-interactive-htmx.md`

## Goal

Refine the new asynchronous diary experience based on hands-on review: eliminate third-party runtime CDN warnings, make AI recommendations lazy, stop requesting complete pages after saves, simplify quick-action controls, improve plant/date disclosure, and optimize photos in the browser before upload.

## Non-Goals

- Replacing Django forms or server-side image validation/storage.
- Adding a background task queue in this slice.
- Changing diary ownership or privacy rules.
- Making edit/delete, plant lifecycle, or filters asynchronous.
- Removing server-side image normalization; client compression is an additional bandwidth optimization, not a trust boundary.

## Current Understanding

- Profile pages load Bootstrap 5.0 beta and Flatpickr from jsDelivr, producing report-only CSP console messages and unnecessary external runtime dependencies.
- Bootstrap is already present in the local frontend workspace; Flatpickr is not.
- Detail rendering computes fallback/cached recommendation state synchronously, and add-action POST generates AI synchronously before returning.
- Successful asynchronous forms currently fetch complete page HTML and select the diary workspace from it.
- Detail quick actions expose watering and a verbose “add another action” button.
- The generic action form always renders plant choices even when “apply to all” is selected.
- Date shortcuts stack beside the photo field instead of forming one compact desktop date row.
- Images are uploaded in their original browser-selected representation; the model later normalizes dimensions but upload bandwidth is not reduced.

## Proposed Approach

### Local frontend assets

- Remove external Bootstrap and Flatpickr tags from the profile base template.
- Continue using the existing compiled Bootstrap styles already included by the Django-owned static bundles.
- Install Flatpickr in `frontend/package.json`; emit its JavaScript, Ukrainian locale, and CSS through webpack and reference only `{% static %}` URLs.
- Keep all emitted assets compatible with the existing static/CDN deployment path so production may serve them through the project’s configured static CDN.

### Lazy recommendation

- Add an authenticated, owner-scoped diary recommendation endpoint returning a dedicated partial.
- Render a lightweight recommendation skeleton/placeholder with `hx-get` and `hx-trigger="load"` on diary detail.
- Move AI generation out of add-action POST. The POST should save and return immediately; the lazy endpoint generates/caches advice for the latest relevant entry.
- Keep deterministic fallback behavior if AI is unavailable.

### Fragment refresh

- Add explicit diary list/detail fragment responses and point post-save refresh URLs at those fragments.
- Return only the replaceable workspace markup, not the complete profile page.
- Preserve normal full-page GET and POST/redirect fallbacks.

### Compact quick actions

- Replace verbose detail quick controls with a single row of icon buttons for watering, fertilizer, harvest/crop, photo, and note, plus an ellipsis button for the full action chooser.
- Give every icon an accessible Ukrainian label and tooltip/title.
- Reuse the generic diary action modal, preselecting the requested action. This gives every action the existing editable date instead of forcing today.
- Keep quick watering’s server endpoint for existing/no-JavaScript compatibility if still referenced elsewhere, but detail icon actions use the generic dated form.
- Use the same icon action set on diary-list cards and keep both detail and list controls in one compact mobile row.

### Progressive form disclosure

- Present “all active plants” and “select plants” as clear mode controls.
- Keep the plant grid hidden while apply-to-all is active and reveal/enable it only after the user selects the non-all mode.
- Preserve Django’s existing `apply_to_all` and `plants` validation contract.

### Date layout

- Group the date picker and Today/Yesterday shortcuts in one horizontal desktop control row.
- Allow wrapping/stacking on narrow screens and retain 44px minimum targets.

### Client image preparation

- Install `browser-image-compression` in the frontend workspace.
- Before asynchronous diary submission, compress selected images off the main thread where supported, cap dimensions/file size, and request WebP output.
- Replace the submitted `FormData` image with the processed file while preserving the original upload when conversion fails or WebP is unsupported.
- Show a local preview with a rotate-90° control and apply the selected orientation before compression/submission.
- Announce compression state and never bypass Django image validation.

## Risks And Unknowns

- Browser WebP encoding and worker support vary; failure must fall back to the original file.
- Re-encoding transparent PNGs to WebP may change size/quality; use conservative settings and skip files already below the threshold when appropriate.
- Lazy AI requests can overlap after rapid actions; recommendation cache keys must remain tied to the latest item so stale responses do not overwrite newer advice.
- Generic modal action preselection must reset between opens and keep harvest-specific fields synchronized.
- Extracting workspace fragments must not duplicate IDs or lose modal/menu initialization.

## Test Strategy

- Assert profile templates contain no jsDelivr Bootstrap/Flatpickr URLs and reference local assets.
- Assert add-action no longer invokes AI generation synchronously.
- Test owner-only recommendation endpoint, empty state, latest-item response, and cached/generated behavior.
- Test fragment GETs return only the intended workspace wrapper.
- Verify action icons and stable accessible labels render; preselection hooks map to valid action values.
- Verify plants are initially hidden/disabled and become available in select-plants mode.
- Verify quick actions retain editable date and ordinary full-form fallback.
- Build frontend assets and confirm Flatpickr/image-compression packages resolve.
- Browser-test desktop single-row date controls, mobile wrapping, lazy recommendation, no full-page HTML refresh, action preselection, plant disclosure, and image submission fallback.
- Run `just test-target core.diary`, targeted lint/template lint, `npm run build:static`, and `just collectstatic`.

## Acceptance Criteria

- Profile diary pages make no runtime Bootstrap/Flatpickr requests to jsDelivr.
- AI recommendation markup loads after the primary diary page and action POSTs are not blocked by AI generation.
- Successful asynchronous actions request only a diary fragment and do not navigate/reload the complete page.
- Detail quick actions are icon-only, accessible, include harvest/crop and an ellipsis full chooser, and open a dated form.
- Plant choices are hidden until select-plants mode is chosen.
- The plant heading and help text are hidden together with the choices until select-plants mode is chosen.
- Desktop date picker and Today/Yesterday controls share one row; mobile remains usable.
- Selected photos are compressed/resized and converted to WebP before asynchronous upload when supported, with safe original-file fallback.
- Users can preview and rotate a selected diary photo before upload.
- Existing authorization, CSRF, validation, multipart upload, and ordinary navigation fallbacks remain green.

## Documentation Updates

- Write execution evidence to `docs/work/results/2026-07-12-diary-interaction-refinement.md`.
- Update the prior result only if an earlier implementation claim becomes inaccurate.
- Add a broader engineering decision only if these frontend conventions expand beyond profile/diary pages.

## Implementation Checklist

- [x] Capture user feedback and screenshots.
- [x] Install and locally bundle Flatpickr and image compression.
- [x] Add lazy owner-scoped recommendation endpoint/partial.
- [x] Remove synchronous recommendation generation from action save.
- [x] Add list/detail fragment responses and refresh URLs.
- [x] Replace detail actions with accessible icons and modal preselection.
- [x] Add explicit plant target mode disclosure.
- [x] Align desktop date controls.
- [x] Add client WebP compression with fallback.
- [x] Add image preview and rotation before compression.
- [x] Add/update tests and build assets.
- [x] Run browser/mobile verification.
- [x] Write result artifact.
