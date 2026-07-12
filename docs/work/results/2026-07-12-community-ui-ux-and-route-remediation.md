# Result: Community UI/UX And Route Remediation

- Date: 2026-07-12
- Plan: `docs/work/plans/2026-07-12-community-ui-ux-and-route-remediation.md`
- Status: Completed

## Delivered

- Removed the community-home hero and introductory content entirely; the publication feed now starts immediately and supplies the page heading.
- Normalized the shared create control to a 44 px desktop control and improved content/card contrast.
- Replaced the heavy tag hover fill with a softer main-site-aligned hover/focus treatment.
- Restyled the mobile bottom navigation to match the main AgroMega navigation palette, elevation, spacing, active state, and touch targets.
- Removed shared desktop/mobile community navigation from publication compose pages so the dedicated editor bar is the only local header.
- Removed the duplicate publication-comment jump action and duplicate discussion-page hero action while retaining the actual comment form and contextual toolbar action.
- Made `/community/` canonical across Nginx, proxy script name, static/media defaults, SSO return validation, local environment configuration, OIDC callback, and sitemap discovery.
- Added permanent path-preserving redirects from `/forum` and `/forum/...` to `/community/` equivalents.

## Verification

- `python manage.py test community forum_sso` in `forum_instance`: 48 tests passed, including hidden-body-comment pagination coverage.
- `python manage.py test core.posts.tests.test_views.SiteMapTests` in `core`: 5 tests passed; only existing CKEditor/auth/time-zone warnings were reported.
- `python manage.py check` in `forum_instance`: no issues.
- `python manage.py collectstatic --noinput`: updated community CSS collected successfully.
- Nginx request to `/forum/topic/active/`: 301 to `/community/topic/active/`.
- Nginx request to `/community/`: 200.
- Browser checks at 1440 × 1000 and 390 × 844: one main landmark, no horizontal overflow, correct active mobile item, 58–61 px mobile tap areas, 72 px bottom bar, and 44 px desktop create control.
- `git diff --check` for both application repositories and Nginx: clean.

## Rollout Notes

- Production environment values and the registered OIDC redirect URI must be changed to the `/community/complete/oidc/` callback in the same deployment.
- The included Nginx compatibility redirects preserve old external links, but CDN/cache rules outside this workspace should be checked during deployment.
- Existing uncommitted July 11 community work was preserved as the baseline; this result describes the July 12 remediation layered on top of it.

## Checker

- Final result: `PASS`.
- One repair cycle corrected canonical SSO/logout environment values and excluded the hidden publication body record before comment pagination.

## Follow-up UI Pass

- Header account/create/search menus now close on outside click or Escape and use the main-site rounded dropdown treatment.
- Publication filters use smaller wrapping chips with bounded vertical overflow for large tag sets.
- Inactive mobile navigation items now use the main-site green rather than gray.
- The publication-list hero and editor top strip were removed; the editor publish action moved into a compact canvas action row.
- Community/list surfaces now use stronger white cards, borders, shadows, and internal spacing against a darker page canvas.

## Community Shell And Search Follow-up

- Removed main-site navigation/profile/settings links from the forum shell; the local brand now links to the community overview.
- Unified search now returns published publication matches and discussion matches in separate result sections.
- Desktop search, create, notification, and account controls remain on the same row after the simplified brand.
- Publication tags now have explicit margins in addition to flex gaps, preventing browser/style collisions from collapsing their spacing.
- Discussion category menus are absolute floating overlays and close on outside click or Escape.
- Account triggers remove stale selected classes and keep the canonical green color after closing.
- Focused forum/community suite: 49 tests passed.
- Added one persistent, low-emphasis “На AgroMega” return link beside the community brand without restoring the removed main-site navigation cluster.
