# Plan: Mobile UX Improvements

- Date: 2026-06-21
- Status: Draft
- Owner: TBD
- Related domain: Cross-domain mobile experience; Advertising Marketplace; Diary And Journals; Catalog Information; Companies And Shops; Events Calendar; Authentication And Identity
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Improve AgroMega's mobile user experience so users can more easily discover content, trust listings, create user-generated content, sign in, and move between public pages, forum pages, marketplace pages, and personal tools.

The first implementation pass should produce a visibly better mobile experience on the public site, introduce reusable UI patterns for repeated elements such as forms and cards, and prepare a second authenticated pass for the personal area after a signed-in browser session is available.

## Non-Goals

- Redesigning the full desktop experience.
- Replacing the whole visual system in one change.
- Creating a large standalone design-system package before the existing templates and CSS are understood.
- Changing marketplace, event, diary, forum, or catalog business rules unless a UX fix exposes a required rule.
- Implementing moderation, expiry, or ownership lifecycle changes for adverts/events beyond UX gating and messaging.
- Changing forum backend behavior unless needed for navigation consistency.

## Current Understanding

The mobile UX review used a `390 x 844` viewport on `http://localhost:8000/` and covered:

- Home page.
- News.
- Adverts listing and advert detail.
- Companies listing and company detail.
- Events listing and event creation page.
- Categories.
- Registry root and registry category.
- Search.
- Feedback.
- About and privacy pages.
- Plant diary landing page.
- Login page.
- Forum root.
- Advert creation page.

The first pass used an unauthenticated session. A follow-up signed-in mobile review covered:

- Account menu from the bottom avatar.
- `profile/adverts`.
- `profile/adverts/create`.
- `profile/diary`.
- `profile/diary/<id>`.
- `profile/plants`.
- `profile/change`.
- `forum/` while signed in to the main site.

Observed high-impact issues:

- Mobile bottom navigation exposes only a narrow subset of product areas.
- Many mobile tap targets are smaller than the expected 44px comfortable touch area.
- Forum mobile navigation differs from the main site and feels like a separate product.
- Logged-out users can reach long create forms where the login requirement is not clearly explained before they invest effort.
- Local adverts can contain rough or test-looking data because the local database is intentionally separate from production.
- Some pages have empty or weak visible headings.
- Search links and icon-only controls need better accessible names and visible context.
- The plant diary page has the strongest mobile presentation and can serve as a quality reference.
- `adverts/create/` logs a JavaScript error from `static/posts/j-detail.js` and repeated CKEditor warnings.
- Repeated elements such as forms, cards, buttons, CTAs, listing rows, and empty states are inconsistent across pages.
- The account menu exposes useful personal destinations, but the personal area does not yet feel like one cohesive dashboard.
- `Мої оголошення` uses compact icon-only actions for update-date, edit, delete, and deactivate; these are small, unlabeled, and easy to mis-tap on mobile.
- Some potentially destructive advert actions are exposed as small links and should be reviewed for confirmation, method semantics, and accessible labels.
- The diary workspace has stronger product value and better content hierarchy, but list pages are long and action-heavy on mobile.
- Diary and plant pages repeatedly use `⋯` buttons that are below comfortable touch size.
- Profile editing exposes raw current-avatar file text and lacks mobile-friendly autocomplete/help text for profile fields.
- Forum remains unauthenticated until the user explicitly follows forum SSO, so the account menu's `Форум` link and the forum page's `Увійти` state may feel confusing after signing in to the main site.

## Assumptions

- Mobile users are a primary audience for browsing AgroMega content and posting marketplace/events content.
- Public browsing should remain possible without login.
- Creating adverts/events should either require login up front or clearly preserve the user's intent after login.
- The sticky bottom navigation is intended to remain part of the mobile experience.
- Forum integration should feel connected to AgroMega even if forum implementation stays in the sibling `forum_instance` project.
- Plant diary is an important product direction and should remain visible, but the persistent promotion should not dominate every page view.
- Shared UI patterns should be introduced incrementally through existing template/CSS conventions rather than a disruptive rewrite.

## Proposed Approach

### Phase 0: Shared UI Inventory And Pattern Baseline

Before changing page-by-page UX, identify repeated UI elements and define the first reusable patterns.

- Inventory existing variants for:
  - Form pages and form fields.
  - Primary, secondary, icon-only, and text-link buttons.
  - Content cards for adverts, companies, news, categories, registry, and diary.
  - Listing pages, detail pages, and creation pages.
  - Empty states, login gates, and helper/error messages.
  - Bottom navigation, headers, CTAs, and promo banners.
- Decide a small set of reusable mobile-first patterns:
  - Form layout: page title, intro/help text, field spacing, labels, required markers, helper text, error text, submit actions.
  - Card layout: image ratio, title, metadata, description length, CTA placement, trust/status signals.
  - Button styles: primary action, secondary action, quiet/text action, icon-only action, destructive action if needed.
  - Page sections: spacing, headings, list/card grids, pagination.
  - Login gate: consistent title, explanation, sign-in action, and return behavior.
- Implement patterns in the least invasive place supported by the current codebase:
  - Shared templates/includes if the existing template structure supports them.
  - Shared CSS classes if templates are currently too varied.
  - Page-specific adapters only where domain information differs.
- Use the plant diary mobile page as a reference for spacing, hierarchy, and CTA clarity, while adapting it to the more utilitarian pages like listings and forms.

### Phase 1: Mobile Navigation And Trust Quick Wins

Improve the shared mobile shell first because it affects most pages.

- Add a clearer mobile navigation model:
  - Keep primary bottom actions for the highest-frequency tasks.
  - Add a menu/account surface that includes `Події`, `Компанії`, `Форум`, `Реєстр`, `Про нас`, `Контакти`, and privacy links.
  - Give the search icon an accessible label and visible affordance where appropriate.
- Normalize tap target sizes:
  - Make bottom navigation items, CTA links, `Докладніше`, pagination, category links, and compact icon controls at least 44px high where possible.
  - Add enough spacing between adjacent text links to prevent accidental taps.
- Reduce banner fatigue:
  - Make the plant diary promo dismissible, smaller after first exposure, or absent on pages where it competes with the main task.
- Fix empty headings:
  - Ensure each public page has one meaningful visible `h1`.
  - Remove empty heading elements from templates.
- Improve listing presentation without hiding local content:
  - Keep local/test-looking data visible because local data is not production data.
  - Ensure advert cards still render clearly with whatever title, image, or placeholder data exists.

### Phase 2: Creation Flow Improvements

Make user-generated workflows easier and safer on mobile.

- Gate create pages more clearly for logged-out users:
  - On `/adverts/create/` and `/events/create/`, show a sign-in prompt before the full form if login is required.
  - Explain what the user can do after signing in.
  - Preserve the intended destination with `next`.
- Improve mobile form usability:
  - Apply the shared form pattern from Phase 0 to adverts, events, feedback, login, and registration.
  - Add useful placeholders, `autocomplete` attributes, and helper text for contact, email, location, price, and date fields.
  - Review required fields and make required markers consistent.
  - Simplify the mobile rich-text toolbar or provide a plain mobile-friendly editor mode.
  - Make submit buttons full-width or easier to reach on mobile.
- Fix frontend runtime issues:
  - Investigate and fix the `static/posts/j-detail.js` undefined `id` error on create pages.
  - Suppress or configure CKEditor export-PDF warnings if the feature is not used.

### Phase 3: Page-Specific Improvements

Improve high-traffic page patterns after the shared shell is stable.

- Home:
  - Keep the hero but review vertical height so search and first content appear sooner.
  - Clarify the primary mobile action: read content, search, post advert, or try diary.
- News:
  - Apply the shared card/list pattern.
  - Improve card scanability with tighter metadata layout and source/date hierarchy.
  - Make source filters/buttons larger and less repetitive.
- Adverts:
  - Apply the shared card/list pattern.
  - Improve card trust signals: title quality, category, location, price/contact presence, updated date, and relevant image.
  - Consider adding filters/search near the top.
- Companies:
  - Apply the shared card/list pattern.
  - Add a clear page title and intro.
  - Improve cards with consistent image sizing and key business details.
- Categories/registry:
  - Add search/filter within long category lists.
  - Make dense category links easier to scan and tap.
- Feedback:
  - Add a visible page title.
  - Add email autocomplete and field helper text.
  - Ensure captcha and submit flow are clear on small screens.
- Forum:
  - Align header/nav with the main site.
  - Improve forum search and login CTA layout.
  - Decide whether the main bottom nav should also appear on forum pages.

### Phase 4: Authenticated Personal Area Improvements

Improve the signed-in mobile workspace so it feels like one coherent personal area rather than separate pages linked from the account menu.

- Create a personal-area landing/dashboard:
  - Show clear entry points for adverts, diaries, plants, profile, and forum.
  - Summarize the user's own content counts and next useful actions.
  - Avoid making users rely only on a footer/account menu to discover personal tools.
- Improve `Мої оголошення`:
  - Replace unlabeled icon-only row actions with a mobile action menu or labeled actions.
  - Give each advert card consistent title, date, status, view count, and primary action.
  - Make delete/deactivate actions require explicit confirmation and use non-GET semantics if they currently mutate state.
  - Add empty states and low-content states for users with no active adverts.
- Improve advert creation inside the personal area:
  - Reuse the shared form pattern from Phase 0.
  - Add helper text and autocomplete for author/contact/location/price.
  - Simplify or replace CKEditor toolbar on mobile.
  - Keep the form visually distinct from public listing pages and make save/publish action sticky or easy to reach.
- Improve diary workspace:
  - Keep the strong dashboard metrics and "needs attention" value.
  - Make diary cards more compact and consistent across `profile/diary`, diary detail, and plant list.
  - Increase `⋯` action buttons to a comfortable touch target and add accessible labels.
  - Consider collapsing repeated per-diary quick-action forms until the user asks to act, so the page is lighter and less form-heavy.
  - Ensure quick watering and add-action modals have clear labels, date inputs, cancel/save hierarchy, and no accidental submit risk.
- Improve plants collection:
  - Add filtering/search for many plants.
  - Standardize plant cards with status, diary links, last action, and "open diary" action.
  - Make back links and diary chips easier to tap.
- Improve profile edit:
  - Add autocomplete attributes for email, name, phone, birthday, and address/location where applicable.
  - Replace raw avatar path/current-file text with a small preview and concise change/remove controls.
  - Clarify required location behavior.
  - Use a full-width save button and a clear unsaved-changes state if feasible.
- Clarify forum identity:
  - Decide whether account-menu `Форум` should automatically start SSO or whether it should explain the handoff.
  - On forum pages, avoid showing `Увійти` as if the user is fully logged out when the main site session exists.

## Risks And Unknowns

- The forum lives in the sibling `forum_instance` project, so shared navigation changes may require coordinated work outside this repository.
- Local/test-looking listing content should not be hidden or filtered as part of UX work because local data is not connected to production.
- Login requirements for adverts/events may be policy decisions, not just template decisions.
- The bottom navigation item set needs product prioritization because mobile space is limited.
- A persistent plant diary promo may be intentional growth strategy; changing it should preserve marketing value while reducing friction.
- Rich text editing on mobile can become a large scope if CKEditor behavior needs deeper replacement.

## Test Strategy

- Use the local Docker Compose environment from the parent `am-dev` project when possible.
- Run targeted backend/template tests for changed views if existing tests cover those areas.
- Add or update view/template tests for:
  - Logged-out create-page behavior.
  - `next` parameter preservation into login.
  - Public listing visibility if draft/test filtering is implemented.
- Add template or snapshot-style checks where practical for shared UI includes/classes.
- Run targeted commands as appropriate:
  - `just test-target core.adverts`
  - `just test-target core.events`
  - `just test-target core.diary`
  - `just test`
- Perform manual mobile browser verification at `390 x 844` and at least one narrower viewport such as `360 x 740`.
- Verify:
  - Shared form and card patterns render consistently across the changed pages.
  - No horizontal overflow on reviewed pages.
  - Bottom nav/menu is reachable and does not cover critical actions.
  - Tap targets are comfortable.
  - Create pages communicate login requirements clearly.
  - Search and icon-only controls have accessible names.
  - Console has no new JavaScript errors on reviewed pages.

## Documentation Updates

- Update this plan as scope is confirmed or split into tickets.
- Write a result artifact under `docs/work/results/` after implementation.
- Update relevant domain notes if implementation clarifies:
  - Advert lifecycle, ownership, moderation, draft/test visibility, contact rules, or expiry.
  - Event creation lifecycle and login requirements.
  - Diary privacy and personal-area ownership rules.
  - Forum integration boundaries.
- Add an engineering decision if the project chooses a durable mobile navigation architecture shared across main and forum surfaces.
- Add an engineering decision if the shared UI pattern work grows into a formal design-system layer.

## Implementation Checklist

- [ ] Confirm the first implementation phase and owner.
- [ ] Inventory repeated forms, cards, buttons, listing rows, and empty states.
- [ ] Define the first shared mobile UI patterns.
- [ ] Decide mobile navigation content and priority.
- [ ] Confirm logged-out create-page behavior for adverts and events.
- [ ] Keep local/test-looking adverts visible while improving how cards handle rough content.
- [ ] Inspect shared mobile templates, CSS, and forum integration points.
- [ ] Implement Phase 1 shared mobile shell improvements.
- [ ] Implement Phase 2 create-flow improvements.
- [ ] Implement selected Phase 3 page-specific improvements.
- [ ] Run targeted automated tests.
- [ ] Run manual mobile verification on public pages.
- [ ] Review authenticated personal area after sign-in is available.
- [ ] Record implementation results and follow-up items.
