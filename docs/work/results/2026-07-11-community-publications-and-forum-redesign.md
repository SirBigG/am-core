# Result: Community Publications And Forum Redesign

- Date: 2026-07-11
- Status: Phases 0–3 foundation implemented; launch hardening remains
- Scope: `am-core`, `forum_instance`, Nginx, and the root Docker Compose integration

## Phase 0 Evidence

The investigation confirmed the local architecture described by the plan:

- `forum_instance` is the existing separate Django/Spirit application and has its own database and dependency set; it is not a service to recreate inside `am-core`.
- Nginx owns the external `/forum/` namespace, redirects `/forum` to `/forum/`, serves forum static/media namespaces, and proxies application requests to the forum service.
- Forum settings participate in script-prefix generation, so prefix preservation must be tested at the proxy boundary rather than inferred only from direct Django client responses.
- Local URL configuration places AgroMega-owned routes before `spirit.urls`, allowing community routes and publication-topic compatibility behavior without modifying installed Spirit source.
- Spirit topics own discussion metadata and the first comment conventionally supplies the topic body. That convention is too coupled to comment editing, deletion, moderation, indexing, and package behavior to become authoritative publication storage.
- The current forum has local Spirit template and identity overrides and an established AgroMega OIDC handoff that must be preserved.
- Spirit 0.14.3 retains a legacy Mistune 0.8.4 rendering dependency. New long-form publication rendering therefore needs an independently maintained renderer and sanitizer.

The production configuration itself has not yet been observed from this workspace. Production header, cookie, CSRF, callback, redirect-status, and prefix behavior remains a pre-launch verification gate.

## Decisions Recorded

The accepted decision record `docs/engineering/decisions/2026-07-11-community-spirit-composition-and-publication-security.md` establishes:

- composition around Spirit using a local companion app and no Spirit model/package modifications;
- publication-owned body content rather than an authoritative first Spirit comment;
- an independent maintained publication Markdown renderer and sanitizer;
- review-required published edits and audited editor corrections;
- immutable canonical slugs with explicit exceptional redirects;
- explicit editorial permissions and object-level authorization;
- a forum-owned sitemap discovered by the main root sitemap index;
- strict `/forum/` URL generation and safe authentication return-target validation.

The business rules, actors, lifecycle, and neighboring ownership boundaries are recorded in `docs/business/domains/community-content/README.md`.

## Repository State Preserved

At the start of implementation, the root `AGENTS.md`, the advanced `am-core` submodule checkout, and the newly added implementation plan were existing changes. They must not be reset or overwritten. Phase 0 documentation changes are additive except for marking the existing plan in progress and updating completed checklist items.

## Implementation Delivered

- Added the broad AgroMega-owned `community` Django app inside the existing `forum_instance`; publications are one capability of this app rather than a separate service or narrowly scoped project.
- Added publication-owned body and metadata, an explicit Spirit topic/body-comment bridge, additive migrations, lifecycle transitions, audit events, immutable Unicode slugs, explicit reviewer permission, author dashboard, review queue, admin integration, and safe plain-text rendering.
- Added published discovery and article presentation, anonymous unpublished-state isolation, canonical redirects from backing Spirit topic URLs, and a forum-owned `/forum/sitemap.xml` containing only published content.
- Added prefix-aware and origin-validated SSO/logout return handling and corrected OIDC success/error redirects for the externally mounted `/forum/` path.
- Rebranded shared navigation as **Спільнота AgroMega**, added responsive community navigation, and renamed the main-site header, footer, and profile links.
- Added the forum sitemap to the main root sitemap index.

## Verification Performed

The additive `community.0001_initial` and `community.0002_alter_publication_slug` migrations were applied successfully to the local forum database.

- Full forum suite: 33 tests passed.
- Focused main sitemap suite: 5 tests passed.
- Django system check: no issues.
- Live Nginx: `/forum` returned 302 to `/forum/`; `/forum/`, `/forum/publications/`, and `/forum/sitemap.xml` returned 200 after migration.
- `git diff --check` passed in the root and `am-core` repositories.

Remaining verification is governed by the plan: the complete main application suite, production OIDC/configuration checks, upload adversarial cases, broader Spirit-list/search suppression, comments on canonical publication pages, and manual mobile/accessibility review.

## Remaining Risks And Gates

- Verify the actual production Nginx and environment configuration before launch.
- Keep existing Spirit discussion rendering within the known legacy-risk boundary and document its remediation timeline.
- Prove transactional cleanup/recovery for publication, topic, and comment creation failures.
- Ensure draft content cannot leak through Spirit search, notification, comment, feed, generic-topic, or media paths.
- Validate safe `/forum/` OIDC return targets, proxy-aware absolute URLs, secure cookies, and CSRF origins end to end.
- Define operational editor assignments, review policy, sensitive-claim policy, rate limits, spam controls, monitoring, and rollback switches.

## Rollout And Recovery Baseline

Delivery remains additive: create publication tables and routes before altering discussion behavior; retain existing topic URLs; use a reversible navigation/deployment switch; preserve drafts and backing topics during rollback. Launch evidence must record migration and lifecycle counts, sitemap URL counts, anonymous smoke results, redirects, upload failures, moderation backlog, and canonical/indexing signals.
