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

## Verification

- `just test-target core.adverts`
- `just test-target core.events`
- `just test-target core.services`
- `just test-target core.pro_auth`
- `just test-target core.posts`
- `just test-target core.diary`
- `just test-target core.utils.tests.test_ckeditor`
- Targeted `djlint` checks for changed templates.
- Manual mobile browser checks at `390px` width for:
  - `/adverts/create/`
  - `/events/create/`
  - `/feedback/`
  - `/profile/change`
  - `/create/`

## Remaining Follow-Ups

- Decide the mobile navigation content and priority for the bottom nav/account menu.
- Continue shared card/list polish for public listing pages: adverts, companies, events, news, categories, and registry.
- Review logged-out create-page behavior and whether forms should show a clearer login gate before users invest effort.
- Reduce plant diary promo fatigue without removing the product pathway.
- Align forum navigation and identity handoff with the main signed-in experience.
- Continue diary and plant workspace touch-target polish for action menus and dense quick actions.
