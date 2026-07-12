# Plan: Community UI/UX And Route Remediation

- Date: 2026-07-12
- Status: Approved
- Owner: AgroMega product and engineering
- Related domain: `docs/business/domains/community-content/README.md`
- Related decisions: `docs/engineering/decisions/2026-07-11-community-spirit-composition-and-publication-security.md`

## Goal

Make the current community release compact, coherent, and visually consistent across desktop and mobile, remove duplicated creation/comment actions and the publication compose header collision, and move the public community namespace from `/forum/` to `/community/` without breaking existing inbound links.

## Non-Goals

- Replacing Spirit or moving forum-owned data into `am-core`.
- Changing publication models, moderation, permissions, or lifecycle rules.
- Adding dependencies or rebuilding the main-site design system.
- Broadly restyling every Spirit administration screen.

## Current Understanding

- The July 11 redesign is present as user-owned, uncommitted work in both repositories.
- The home hero duplicates creation actions already available in the shared header and consumes most of the first desktop viewport.
- The shared create control is oversized, publication/discussion list surfaces need stronger contrast, tag hover states are too heavy, and the mobile bottom navigation does not match the main-site treatment.
- Publication creation renders the shared community tabs above its dedicated compose bar, producing a second header.
- Publication comments and discussion listings expose duplicated actions for the same destination.
- `/forum/` is currently embedded in Nginx, forum settings, authentication return-path validation, sitemap discovery, tests, docs, and generated asset URLs.

## Assumptions

- `/community/` is the new canonical public namespace.
- `/forum` and `/forum/...` remain compatibility entry points and permanently redirect to the equivalent `/community/...` path.
- Internal Django route names and the `forum_instance` service name remain unchanged.
- The shared header create menu is the canonical global create action; contextual actions remain only where they are not duplicated on the same screen.

## Proposed Approach

1. Update the public proxy, forum settings/default URLs, core sitemap discovery, authentication return-path validation, and relevant tests to canonicalize `/community/` while retaining `/forum/` redirects.
2. Simplify the community home by replacing the oversized hero/action block with a compact introduction integrated into the content surface.
3. Normalize shared action sizing, content cards/surfaces, hover/focus states, and mobile bottom navigation using the existing AgroMega palette and spacing.
4. Suppress shared community navigation on publication compose screens so the dedicated editor bar is the only local header.
5. Remove the comments jump button and the duplicate discussion-list creation button while preserving the actual forms/actions.
6. Run targeted forum/core tests, static checks, and browser review at mobile and desktop widths.

## Risks And Unknowns

- Existing absolute URLs, OIDC callback registration, and production Nginx configuration must all move together; compatibility redirects reduce link risk but deployment configuration still needs coordinated rollout.
- Browser-authenticated authoring validation may depend on the local OIDC session.
- Existing unrelated edits make broad automatic rewrites unsafe; changes will be limited to directly relevant files.

## Test Strategy

- Assert canonical `/community/` routes and exact-one-prefix behavior for login, create, static/media, sitemap, and return URLs.
- Assert legacy `/forum/` compatibility redirects at the proxy/configuration level where feasible.
- Assert removed duplicate labels/actions in rendered home, publication detail, publication compose, and discussion list templates.
- Run forum Django tests/checks and targeted `am-core` view/sitemap tests through Docker.
- Review desktop and mobile renderings, keyboard focus, hover states, header height, bottom navigation, and create/comment journeys in the integrated browser.

## Documentation Updates

- Supersede the `/forum/` namespace invariant in the community domain and engineering decision records.
- Add a dated result artifact with checks, compatibility notes, and any rollout caveats.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update route and rendering tests.
- [x] Implement canonical route and compatibility redirects.
- [x] Implement the UI/UX remediation.
- [x] Run targeted verification.
- [x] Complete independent checker review and one repair cycle if needed.
- [x] Update results and durable documentation.
