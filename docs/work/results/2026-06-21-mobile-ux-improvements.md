# Result: Mobile UX Improvements

- Date: 2026-06-21
- Plan: `docs/work/plans/2026-06-21-mobile-ux-improvements.md`
- Branch: `adverts-pages-update`

## Completed

- Improved mobile personal advert management with card-style actions and POST-only mutating actions.
- Removed empty profile-page heading output by letting profile pages own their layout.
- Simplified the public CKEditor toolbar for mobile-heavy create forms.
- Added accessible labels for mobile footer navigation controls.
- Introduced shared public form panel styles and applied them to advert, event, and feedback forms.
- Kept local/test-looking content visible by plan, since local data is not connected to production data.
- Improved the signed-in profile edit form with helper text, autocomplete attributes, a mobile datepicker hook, and a custom avatar upload/preview control.
- Reworked the `/create/` chooser into a mobile-friendly action panel with clear event and advert entry points.
- Introduced shared public listing card styles and applied them to adverts, events, companies, news, and post/category listing helpers.
- Replaced small listing text links with larger mobile-friendly card actions while keeping local/test-looking content visible.
- Added shared mobile link-grid styles for long category/catalog lists.
- Applied larger 48px tap targets to posts catalog category links and registry category/variety links.
- Improved the mobile footer navigation with consistent 60px controls and a fuller sections menu for categories, events, companies, forum, registry, about, and contact links.
- Added mobile-friendly sign-in prompts on public advert and event create forms with `next` links back to the current form, without blocking anonymous posting.
- Added shared mobile detail/product styles and applied them to event and company detail pages.
- Reduced plant diary promo fatigue with a compact, dismissible site banner that remembers dismissal when browser storage is available.
- Improved diary workspace mobile action targets so diary, entry, and plant overflow controls are visible and 48px on mobile.
- Reworked `/search/` into the shared public form panel with a mobile-stacked search input and visible submit label.
- Tightened the home hero on mobile and added clear first-viewport actions for creating content, browsing categories, and opening the plant diary.
- Added a real personal dashboard at `/profile/` with mobile-friendly entry cards for adverts, diaries, plants, profile settings, creation, and forum handoff.
- Added current-page state to the mobile bottom navigation and normalized bottom-nav avatar/icon sizing.
- Expanded the personal-area sidebar into a full shortcut navigation for dashboard, adverts, advert creation, diaries, plants, settings, and forum handoff, with a horizontal mobile rail.
- Cleaned the mobile bottom/profile navigation by keeping bottom-nav controls brand green without underlines, moving section links out of the profile menu, adding a mobile top gutter below the header, and centering the diary overview content.

## Verification

- `just test-target core.adverts`
- `just test-target core.events`
- `just test-target core.services`
- `just test-target core.pro_auth`
- `just test-target core.posts`
- `just test-target core.news`
- `just test-target core.companies`
- `just test-target core.registry`
- `just test-target core.diary`
- `just test-target core.utils.tests.test_ckeditor`
- Targeted `djlint` checks for changed templates.
- Manual mobile browser checks at `390px` width for:
  - `/adverts/create/`
  - `/events/create/`
  - `/feedback/`
  - `/profile/change`
  - `/create/`
  - `/adverts/`
  - `/companies/`
  - `/news/`
  - `/categories/`
  - `/registry/`
  - Mobile footer navigation on `/registry/`
  - Signed-in `/adverts/create/` and `/events/create/` form rendering
  - Company detail page from `/companies/`
  - Plant diary banner layout and dismiss behavior on `/companies/`
  - Diary list and diary detail action target sizes at `390px` width.
  - `/search/?q=...` search panel at `390px` width.
  - Home hero height, search controls, and action buttons at `390px` width.
  - `/profile/` dashboard cards and forum handoff at `390px` width.
  - Mobile bottom navigation active states on `/search/`, `/adverts/`, and `/profile/`.
  - `/profile/change` personal-area shortcut navigation at `390px` width, including active state and no page-level horizontal overflow.
  - Screenshot follow-up checks for `/adverts/create/`, `/profile/`, and `/profile/diary` at `390px` width: bottom-nav color/underline state, profile menu contents, form top spacing, and diary centering.

## Remaining Follow-Ups

- Decide final mobile navigation content and priority for the bottom nav/account menu.
- Decide whether public advert/event create pages should stay available with sign-in prompts or move to a stronger login gate.
- Align forum page navigation and signed-in display inside the sibling `forum_instance` project.
