# Plan: Interactive Asynchronous Diary With HTMX

- Date: 2026-07-12
- Status: Accepted for implementation
- Owner: TBD
- Related domain: Diary And Journals
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`; `docs/work/plans/2026-06-28-static-build-migration.md`

## Goal

Make the authenticated diary feel immediate and comfortable on mobile by submitting its most common modal actions asynchronously, updating only affected page regions, preserving Django form validation and authorization, and improving date entry on touch devices.

The first delivery should let a user add a diary action or record quick watering without a full-page refresh. Successful submissions should close the modal, refresh the relevant timeline and summary information, and provide accessible feedback. Invalid submissions should remain in the modal and show the server-rendered form errors.

## Non-Goals

- Rebuilding the diary as a single-page application or introducing a JavaScript application framework.
- Creating a JSON API or duplicating Django validation and domain rules in JavaScript.
- Making every diary operation asynchronous in the first delivery.
- Changing diary ownership, privacy, plant lifecycle, recommendation, or other business rules.
- Moving recommendation generation to a task queue in the first delivery. Its latency will be measured and handled with loading feedback; background processing is a possible follow-up.
- Changing public diary pages or the sibling forum project.
- Removing normal POST/redirect navigation. It remains the fallback when JavaScript or HTMX is unavailable.

## Current Understanding

- The diary is server-rendered by Django under `core/diary` and its authenticated profile templates.
- Add-entry and quick-watering forms already render in modals, but their successful POST handlers return redirects, causing a full-page navigation.
- Existing JavaScript in `core/pro_auth/static/pro_auth/profile/diary.js` manages modal state, conditional form fields, menus, and confirmation interactions. It does not asynchronously submit diary forms.
- Diary entry creation performs authorization and validation on the server, saves the entry, updates the diary timestamp, generates/caches a plant recommendation, and then redirects.
- Diary detail includes several pieces of derived UI that can change after an action: timeline/history, dashboard statistics, plant last-action information, and recommendation content.
- Date fields opt into Flatpickr through `data-profile-datepicker`. The shared initialization sets `disableMobile: true`, forcing the custom calendar on touch devices.
- Frontend source dependencies are managed in `frontend/package.json` and compiled through the existing webpack/static workflow. New first-party frontend integration should follow that workflow rather than add another CDN dependency.
- Diary records are user-owned. Partial-response endpoints must retain the same queryset ownership checks, CSRF protection, and safe redirect behavior as full-page requests.

## Assumptions

- HTMX is acceptable as a small interaction layer for server-rendered fragments.
- HTMX will be installed through the existing frontend npm workspace and included in the Django-owned static bundle, rather than loaded from a CDN.
- A separate Python HTMX package is not required initially. Views can detect the `HX-Request` header through a small local helper; this can be reconsidered if HTMX usage expands across the project.
- The initial asynchronous scope is authenticated diary detail and diary list quick actions: add diary action and quick watering.
- Native mobile date inputs are preferable on capable touch browsers. Flatpickr remains the enhanced desktop experience and fallback where appropriate.
- The existing full-page URLs, form actions, response redirects, and browser history semantics remain canonical.
- The visible Ukrainian copy should remain consistent with the current diary UI.

## Proposed Approach

### 1. Establish the HTMX integration

- Add HTMX to `frontend/package.json` and its lockfile, import it from the existing Django-owned JavaScript entry point, and produce it through the established webpack build.
- Configure CSRF submission using the existing form token and normal form serialization; do not create a parallel token mechanism.
- Add a small, documented server-side helper or mixin for detecting HTMX requests consistently.
- Define a reusable loading convention:
  - disable or mark the submitting button as busy;
  - expose an `aria-busy` state;
  - prevent accidental duplicate submission;
  - restore controls after an error;
  - show a visible but unobtrusive success or failure status.
- Keep behavior scoped to explicitly annotated diary elements so existing modal JavaScript and unrelated forms are not changed accidentally.

### 2. Split changing UI into server-rendered fragments

- Extract the diary detail timeline/history into a partial with a stable replacement target.
- Extract the detail dashboard/summary into a partial with a stable replacement target.
- Extract recommendation output into a partial if it changes as part of entry creation.
- Extract plant last-action/card content only if the first implementation proves it must refresh for correctness; otherwise schedule it as the next slice.
- Keep fragment context construction centralized in view/service helpers so full-page and HTMX responses use the same query rules and presentation data.
- Avoid copying large sections of template markup between the complete page and partial responses.

### 3. Make add-action modal submission asynchronous

- Annotate the modal form with HTMX attributes while retaining its ordinary `method`, `action`, encoding, and CSRF token.
- Continue to support multipart upload for diary action photos.
- On a valid HTMX POST:
  - perform the same save, timestamp update, recommendation generation, and cache behavior as today;
  - return the refreshed primary fragment;
  - update other affected targets with out-of-band swaps where this keeps the response cohesive;
  - emit a response signal that closes and resets the modal, restores focus to the opener, and announces success.
- On an invalid HTMX POST:
  - return the bound modal form partial with an appropriate non-success status that HTMX is configured to swap;
  - keep the modal open;
  - preserve entered values and display Django field/non-field errors;
  - reinitialize dynamic controls, date enhancement, file labels, and conditional fields in the swapped content;
  - move focus to the error summary or first invalid field.
- On an ordinary POST, retain the current redirect and full-page error behavior.

### 4. Make quick watering asynchronous

- Apply the same progressive-enhancement contract to quick watering on diary detail and diary list cards.
- Reuse the existing server-side ownership, active-diary, active-plant, and selection checks.
- Refresh only the card/detail regions affected by the watering action and provide an accessible confirmation.
- Ensure repeated clicks cannot create duplicate watering entries while a request is in flight.
- Preserve `next`/safe redirect behavior for non-HTMX requests.

### 5. Improve mobile date input

- Stop globally forcing Flatpickr on mobile by removing the unconditional `disableMobile: true` behavior or selecting the enhancement based on input/device capability.
- Render diary dates with a native-compatible `type="date"` value contract (`YYYY-MM-DD`) and allow capable mobile browsers to present their native picker.
- Retain localized Flatpickr formatting and typed-date support for desktop where it improves the experience.
- Add compact date shortcuts for common diary actions, initially `Сьогодні` (Today) and `Вчора` (Yesterday), without changing the submitted date format.
- Keep new actions defaulted to the local current date.
- Ensure date triggers, shortcuts, calendar navigation, and selectable days meet a minimum 44px touch target, with 48px preferred where layout permits.
- Verify that swapped modal fragments reinitialize date behavior exactly once.

### 6. Preserve accessibility and navigation behavior

- Keep modal focus trapping/return behavior and Escape/backdrop closing behavior functional after swaps.
- Announce asynchronous success and errors through an `aria-live` status region.
- Preserve a usable loading state under slow recommendation generation.
- Do not push a browser-history entry for modal submissions.
- Keep filters and ordinary links as navigations during the first slice unless explicitly included in implementation scope.

### 7. Follow-up slices after the first delivery

Once the add-action and quick-watering slice is stable, assess and prioritize:

1. Asynchronous entry edit and delete.
2. Asynchronous plant move/archive/restore operations.
3. Asynchronous diary filters and pagination with URL/history updates.
4. Optimizing or backgrounding recommendation generation if measured latency remains noticeable.
5. Reducing repeated modal markup on the diary list by loading a single form/modal on demand.

These follow-ups should reuse the fragment and event conventions established in the first slice rather than introduce separate request patterns.

## Response Contract

The implementation should make the full-page and HTMX paths explicit:

| Request | Valid result | Invalid result |
| --- | --- | --- |
| Ordinary form POST | Existing safe redirect to diary list/detail | Existing full form page or redirect-compatible behavior with Django errors |
| HTMX add-action POST | Updated diary fragments plus close/success signal | Bound modal form fragment; modal stays open |
| HTMX quick-watering POST | Updated card/detail fragments plus success signal | Modal/form fragment or inline error preserving the user's selection |

Exact status codes and swap behavior must be covered by tests. If invalid forms use HTTP 422, a small HTMX response-error handler must deliberately allow that response body to swap; otherwise return 200 with a clear invalid-form marker. The project should choose one convention and use it consistently.

## Risks And Unknowns

- Recommendation generation currently happens inside add-entry submission. A slow external or AI-backed result can still make an asynchronous request feel slow and can increase the chance of a retry. Loading UI and duplicate-submit prevention are required; latency should be measured before deciding on a background job.
- Multipart image uploads must be tested explicitly through HTMX.
- A single action changes several derived areas. Missing one target could leave the page internally inconsistent until reload.
- The diary list renders a modal/form per active diary. Swapping card content can invalidate event listeners or duplicate element IDs unless initialization is event-driven and scoped.
- Existing JavaScript attaches listeners during initial page load. Replaced fragments will require idempotent initialization on HTMX lifecycle events or event delegation.
- Flatpickr creates an alternate input. Switching between native and enhanced modes can produce duplicated controls or mismatched displayed/submitted values if initialization is not idempotent.
- iOS Safari and Android Chrome differ in native date-picker presentation and support. Both require manual verification.
- HTMX response fragments can accidentally weaken authorization if a new partial endpoint uses a broader queryset. Existing user ownership filtering must be reused.
- Out-of-band swaps can become hard to reason about if too many independent regions are returned. Prefer one primary target and only the minimum necessary secondary updates.
- CDN-loaded Flatpickr remains an existing availability/privacy concern. Moving it into the local frontend bundle may be considered during implementation, but is not required unless needed for reliable mobile behavior.

## Test Strategy

### Django tests

- Add-action ordinary POST still saves and redirects correctly.
- Add-action HTMX POST saves once and returns the expected fragment targets without a redirect.
- Invalid HTMX add-action returns the bound form, preserves values, and performs no write.
- HTMX photo upload saves and returns the expected response.
- Add-action remains restricted to a diary owned by the authenticated user.
- Recommendation cache/update behavior remains equivalent between ordinary and HTMX submissions.
- Quick-watering ordinary POST fallback remains unchanged.
- Quick-watering HTMX POST creates exactly one action and refreshes the expected targets.
- Invalid or unauthorized quick watering cannot mutate another user's diary or plants.
- Archived diary and inactive-plant rules remain enforced.
- Fragment rendering uses the same filters, ordering, grouping, dashboard values, and ownership rules as the complete page.
- Relevant responses retain CSRF protection and do not introduce unsafe redirect handling.

### JavaScript and interaction verification

- Modal opens, submits, shows loading state, closes on success, resets, and returns focus to its opener.
- Double-clicking submit while a request is active does not create duplicate actions.
- Invalid form swaps into the open modal and focuses useful error feedback.
- Conditional action/harvest/plant fields still work after a fragment swap.
- File selection and multipart upload work after a fragment swap.
- Date shortcuts set the correct local calendar date and submitted `YYYY-MM-DD` value.
- Date enhancement initializes once on initial load and once for newly swapped content without duplicate inputs.
- Escape, backdrop close, card menus, and existing confirmation modals continue to work.
- Success/error announcements are available to screen readers.
- With JavaScript disabled, forms still submit and navigate successfully.

### Mobile and visual verification

- Test diary list and detail at approximately 390px width.
- Verify native date selection on current iOS Safari and Android Chrome where available.
- Verify desktop Flatpickr behavior in a current Chromium browser and one additional desktop browser.
- Confirm modal content remains scrollable with the on-screen keyboard open.
- Confirm all primary controls and date shortcuts have comfortable touch targets and no horizontal overflow.
- Confirm the timeline, dashboard, plant status/last action, and recommendation agree immediately after a successful action.

### Repository commands

- `just test-target core.diary`
- `just static-install`
- `just static-build`
- `just collectstatic`
- Run the repository's relevant template/static checks if the implementation changes shared profile templates or built assets.

## Acceptance Criteria

- Adding a diary action from the detail modal does not perform a full-page navigation when HTMX is available.
- Quick watering does not perform a full-page navigation when HTMX is available.
- The timeline and every included derived summary update immediately and consistently after success.
- Invalid forms remain visible in the modal with server-rendered errors and preserved input.
- The submit button clearly communicates progress and cannot submit the same form twice concurrently.
- Photo uploads continue to work.
- Mobile users receive a native-friendly date experience plus Today/Yesterday shortcuts.
- Desktop date entry remains localized and usable.
- Keyboard focus and screen-reader status feedback remain coherent through modal swaps.
- Both workflows still function through ordinary Django POST/redirect when JavaScript is unavailable.
- Ownership, CSRF, archived-diary, active-plant, and safe-redirect protections remain covered by tests.
- Targeted diary tests and the static build complete successfully.

## Rollout And Recovery

- Deliver add-action and quick-watering as one bounded first slice, without converting unrelated diary operations.
- Keep server-rendered full-page fallbacks in the same views so HTMX can be disabled or attributes removed without losing core functionality.
- Avoid a data migration; this should remain a presentation/request-response change.
- If asynchronous behavior causes production issues, remove or disable the HTMX annotations while retaining the backend fallback paths.
- Record implementation details, verification evidence, measured recommendation latency, and deferred follow-ups in `docs/work/results/2026-07-12-diary-interactive-htmx.md`.

## Documentation Updates

- Update `docs/business/domains/diary-and-journals/README.md` only if implementation confirms new workflow or lifecycle rules beyond presentation behavior.
- Add an engineering decision record if HTMX becomes a broader project-wide interaction standard rather than a diary-local technique.
- Add the execution and verification record under `docs/work/results/2026-07-12-diary-interactive-htmx.md`.
- Document any shared fragment, event, loading, or invalid-response convention that future HTMX work must follow.

## Implementation Checklist

- [x] Confirm the product direction: progressive HTMX enhancement with mobile date improvements.
- [x] Confirm exact first-slice replacement targets on diary list and detail.
- [x] Add HTMX to the frontend workspace and static bundle.
- [x] Add shared HTMX request detection and response conventions.
- [x] Reuse coherent diary list/detail workspace targets so all derived regions refresh together.
- [x] Add tests for ordinary and HTMX add-action POST paths.
- [x] Implement asynchronous add-action submission, errors, loading, modal reset, and focus behavior.
- [x] Add tests for ordinary and HTMX quick-watering POST paths.
- [x] Implement asynchronous quick watering and affected-region updates.
- [x] Replace forced mobile Flatpickr with native-friendly behavior.
- [x] Add Today/Yesterday shortcuts and idempotent date initialization.
- [x] Verify existing multipart/recommendation tests remain green with the new response path.
- [x] Run targeted diary tests and static asset build/collection.
- [x] Perform available desktop and 390px mobile interaction/accessibility checks.
- [x] Write the result artifact with verification evidence and follow-ups.
- [ ] Update durable domain or decision docs if implementation reveals new rules.
