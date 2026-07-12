# Plan: AgroMega Community, Publications, And Forum Redesign

- Date: 2026-07-11
- Status: In Progress
- Owner: AgroMega engineering
- Related domain: Community-generated knowledge and discussion
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Evolve the existing Django Spirit forum into **Спільнота AgroMega**, a coherent community area that supports conventional discussions and moderated, article-like user publications while remaining a separately deployed Django application served exclusively below the main site's `/forum/` proxy path.

The result should make the entire forum easier and more credible to use, give publications a dedicated editorial and SEO experience, reuse existing Spirit accounts/topics/comments where appropriate, and avoid coupling new product rules directly to Spirit internals.

## Product Direction

Use **Спільнота** as the primary navigation and product label. The initial community contains two clearly different experiences:

- **Публікації**: durable authored guides, rankings, expert material, company editorial content, and personal experience. Publications use article-style presentation and pre-publication moderation.
- **Обговорення**: existing forum topics and replies, published through the normal discussion workflow.

Possible future types such as questions and answers may be considered later, but should not expand the first implementation unless the initial model naturally supports them without additional workflow complexity.

Suggested Ukrainian positioning:

> Спільнота AgroMega — публікації, практичний досвід і обговорення про сільське господарство.

## Non-Goals

- Moving the forum into the `am-core` Django process or database.
- Serving any public forum or publication page outside `/forum/`.
- Forking Spirit or editing installed package source as the primary customization mechanism.
- Adding fields directly to Spirit-owned database models.
- Replacing Spirit during the first delivery phase.
- Building a fully open, unmoderated publication system.
- Rebuilding main-site catalog, marketplace, diary, company, or event functionality.
- Creating a second copy of publication content in `am-core`.
- Introducing `/community/` or `/publications/` top-level routes on the main application.

## Current Understanding

### Deployment And Routing

- `forum_instance` is a separate Django project in the sibling `../forum_instance` directory with its own dependencies and database.
- Nginx redirects `/forum` to `/forum/`, proxies `/forum/` to `forum_instance`, and strips the prefix before forwarding requests.
- Nginx sends `X-Script-Name: /forum`; forum settings use `FORCE_SCRIPT_NAME` plus `/forum/static/` and `/forum/media/` paths.
- The `/forum/` boundary is a product and architecture invariant. Generated URLs, redirects, authentication callbacks, static/media URLs, canonical URLs, sitemap URLs, forms, pagination, and JavaScript requests must preserve it.
- The main application provides OIDC identity; the forum keeps its own local Spirit user records and uses its own session.

### Spirit Integration

- The forum currently uses `django-spirit==0.14.3`.
- Spirit's `Topic` model provides author, category, title, slug, timestamps, moderation flags, and counters, but no content type or editorial workflow.
- A topic body is stored in its first Spirit `Comment`; later comments are replies.
- The local forum already overrides Spirit base, header, form, topic publish/update, administrative, and profile templates.
- Custom routes are already placed before `include("spirit.urls")`, so local community/publication routes can take precedence without modifying the package.
- The package currently pins the legacy Mistune 0.8.4 parser. Existing project documentation records security findings and upgrade constraints around this dependency. New publication behavior must not deepen reliance on Spirit-specific parser internals.

### Current Experience

- The forum visually identifies itself as “Форум” and largely exposes Spirit's traditional category/topic structure.
- Its header has been customized to link back to AgroMega, but the overall page hierarchy, discovery, content creation, topic presentation, mobile behavior, metadata, and editorial affordances require a broader redesign.
- The main site's header and footer still link to the product as “Форум”.

## Architecture Principles

1. **Keep the proxy boundary:** every community route is publicly rooted at `/forum/`.
2. **Compose around Spirit:** use Spirit for discussions, replies, users, notifications, likes, and existing moderation primitives; keep publication-specific state in an AgroMega-owned app.
3. **One canonical page:** a publication has one indexable article URL within `/forum/`; do not index a duplicate generic topic page.
4. **Separate product state from transport state:** publication status and metadata must not be encoded only as categories or Spirit removal flags.
5. **Preserve existing content and URLs:** current topic/category/profile URLs continue working unless an explicit redirect map is tested and deployed.
6. **Progressive migration:** redesign existing discussion views without requiring a risky all-at-once Spirit replacement.
7. **Accessible, mobile-first UI:** the redesign must work well for reading and authoring on narrow screens.

## Proposed URL Structure

All URLs below are public paths after Nginx proxying:

```text
/forum/                                  community home
/forum/publications/                     published publication listing
/forum/publications/add/                 create publication
/forum/publications/mine/                current user's drafts/submissions
/forum/publications/<slug>/              canonical publication detail
/forum/publications/<slug>/edit/         author/editor update
/forum/publications/<slug>/submit/       submit draft for review
/forum/discussions/                      discussion discovery entry point
/forum/topic/<id>/<slug>/                existing Spirit topic compatibility
/forum/sitemap.xml                       forum sitemap index, if needed
/forum/sitemaps/publications.xml         published publications only
/forum/sitemaps/discussions.xml          eligible public discussions, optional
```

Final route names should follow Django conventions and avoid collisions with Spirit. Slug uniqueness must be defined explicitly; publication URLs should not depend solely on a mutable title without a redirect strategy.

## Proposed Data Ownership

Add an AgroMega-owned Django app inside `forum_instance`, tentatively named `community` or `publications`. It should use a companion model rather than subclassing or modifying Spirit's `Topic` table.

Minimum publication metadata:

- one-to-one link to the backing Spirit topic;
- stable slug or other canonical URL identifier;
- lifecycle status: draft, in review, changes requested, published, rejected, archived;
- publication type: guide, ranking/selection, expert article, personal experience, or company editorial;
- excerpt/summary;
- cover image and accessible alternative text;
- author-facing editorial notes, kept non-public;
- publication and significant-update timestamps;
- optional SEO title and description with sensible automatic defaults;
- company/editorial and featured flags;
- optional disclosure label for commercial or sponsored relationships;
- optional related catalog references, designed across the database boundary rather than as direct foreign keys to `am-core` tables.

The backing topic owns the title and discussion thread. The first ordinary Spirit comment can remain the body for MVP compatibility, but the implementation investigation must confirm and enforce the invariant safely. If reliable first-comment editing, previewing, moderation, and rendering cannot be guaranteed, publication body ownership should move to the local publication model while replies remain in Spirit.

Cross-database relationships to catalog objects should use stable typed identifiers or URLs plus validation, not Django foreign keys across separate databases.

## Publication Lifecycle And Permissions

Initial lifecycle:

```text
draft -> in_review -> published
                  -> changes_requested -> draft
                  -> rejected
published -> archived
```

Rules:

- Any authenticated AgroMega user synchronized through OIDC may create a draft and submit it.
- User publications require staff/editor approval before becoming publicly accessible or entering a sitemap.
- Authors may edit drafts and changes-requested publications.
- Editing a published publication needs an explicit policy: either return it to review or permit only trusted editors to update it directly. Decide before implementation.
- Company and trusted-editor accounts may publish directly only through an explicit permission, not by fragile username/category checks.
- Draft, review, rejected, and archived pages must not leak to anonymous users, search, feeds, or sitemaps.
- Editors need a visible review queue and a minimal audit trail of status changes.
- Spirit replies to a published publication are displayed as comments; publication replies must follow existing flagging and moderation rules.
- Decide whether replies are allowed while a publication is not published; default to no.

## Forum And Community UX Redesign

Treat the visual work as a product redesign rather than a label replacement.

### Shared Shell

- Rename visible “Форум” references to “Спільнота” in `am-core` and `forum_instance`.
- Align forum header, footer, typography, spacing, color, buttons, cards, breadcrumbs, focus styles, and responsive navigation with the main AgroMega site.
- Make `/forum/` feel like part of one site while retaining clear deployment ownership.
- Provide obvious entrances to “Публікації” and “Обговорення”.
- Review authentication handoff, profile links, notifications, search, and return URLs on desktop and mobile.
- Replace inline layout hacks where practical and keep forum-specific assets within `forum_instance`.

### Community Home

- Introduce the community purpose in Ukrainian.
- Feature recent or editorial publications separately from active discussions.
- Provide clear primary actions: “Додати публікацію” and “Почати обговорення”.
- Show categories/topics without making Spirit's internal hierarchy the only discovery mechanism.
- Design useful empty states suitable for a small early community.

### Publications

- Dedicated card-based listing with cover, type, author, excerpt, and publication date.
- Article detail with cover, author identity, publication/update dates, disclosure/type label, readable body, sharing metadata, related content, and comments.
- Authoring UI should clearly distinguish article title, summary, cover, body, and type from an ordinary forum topic form.
- Include preview and save-draft behavior; do not rely only on Spirit's browser-local textarea storage.
- Provide author dashboard/status feedback and an editor review experience.

### Discussions

- Improve category, topic listing, topic detail, reply form, and profile presentation.
- Preserve familiar forum capabilities while simplifying Spirit terminology and visual clutter.
- Clarify topic author, dates, activity, reply count, state, and moderation actions.
- Audit pagination, unread state, likes, polls, notifications, private topics, and administrative screens so custom styling does not break them.

### Accessibility And Responsive Behavior

- Keyboard-accessible navigation, menus, forms, dialogs, editor controls, and pagination.
- Visible focus, correct landmarks/headings, labels, error association, and adequate contrast.
- Comfortable article line length and typography.
- Mobile verification at representative 320–430px widths and desktop verification.
- Images must reserve space, use responsive sizing, and require meaningful alternative text where appropriate.

## SEO And Sitemap Plan

- Publication canonical URLs remain under `/forum/publications/.../`.
- Serve a forum-owned sitemap or sitemap index under `/forum/` because the forum owns publication visibility and update timestamps.
- Add the forum sitemap endpoint to the main site's root sitemap index if the existing sitemap architecture supports nested sitemap references; otherwise document and submit both sitemap locations consistently.
- Include only published, anonymous-accessible, canonical URLs.
- Exclude drafts, previews, review queues, author dashboards, search results, private topics, removed content, pagination/filter combinations, and authentication/profile settings.
- Decide separately whether public discussions meet the quality threshold for sitemap inclusion.
- Publication pages should provide canonical, robots, Open Graph, Twitter/social, and `Article`/`BlogPosting` JSON-LD metadata.
- Structured data must identify the real author and distinguish company editorial content from user experience.
- Add `lastmod` from meaningful publication updates, not comment activity.
- Prevent the backing generic Spirit topic route from producing an indexable duplicate. Prefer routing it to the canonical publication page or emitting a canonical/noindex policy after verifying compatibility with comment links and notifications.
- Update `robots.txt` sitemap declarations as required.

## Proxy And Nginx Requirements

- `/forum` must continue redirecting to `/forum/`.
- `/forum/`, `/forum/static/`, and `/forum/media/` remain the only public forum namespaces.
- New publication routes require no separate top-level Nginx location; they pass through the existing `/forum/` proxy.
- Verify correct behavior for `SCRIPT_NAME`, `PATH_INFO`, `X-Forwarded-Host`, `X-Forwarded-Proto`, secure cookies, CSRF trusted origins, and absolute URI construction.
- Verify that Django `reverse()`, form actions, redirects, login `next`, OAuth/OIDC callback flow, sitemap URLs, canonical URLs, pagination, AJAX requests, uploaded media, and static assets all retain `/forum` externally.
- Add regression tests for prefix preservation. Direct unprefixed forum routes must not accidentally become part of the public contract.
- Review permanent versus temporary redirect status only after local and production route behavior is confirmed.

## Security And Package Sustainability

Before expanding user-generated long-form content, address or explicitly time-box the existing Spirit/Mistune risk:

- inventory every path that converts Markdown to HTML, including preview, edits, history, search indexing, quotations, notifications, and existing stored comments;
- retain and expand regression coverage for raw HTML, unsafe protocols, malformed links/images, and other sanitizer bypasses;
- determine whether the publication MVP can safely use the current renderer under an accepted temporary risk, whether the minimal rendering stack should be vendored/forked and upgraded, or whether publication bodies need an independent maintained renderer;
- document the decision in `docs/engineering/decisions/` before production publication launch;
- avoid allowing arbitrary embedded HTML, scripts, iframes, remote forms, or unsafe media;
- add upload validation, file-size/dimension limits, safe filenames, and authorization checks for cover replacement/deletion;
- apply rate limiting and spam controls to submission, comments, flags, and login handoff as appropriate;
- verify object-level authorization for every draft, preview, edit, submit, review, publish, reject, and archive endpoint.

## Delivery Phases

### Phase 0: Investigation And Decisions

- Confirm production Nginx and environment configuration matches the local `/forum/` behavior.
- Map Spirit URLs, views, forms, templates, signals, search indexing, comment creation/update behavior, permissions, and moderation extension points.
- Characterize the first-comment-as-body invariant, including deletes, moves, moderation actions, history, indexing, and links.
- Inventory existing forum content and URL/indexing behavior.
- Decide publication body ownership and Markdown/rendering strategy.
- Decide published-edit policy, slug/redirect policy, editor permissions, and sitemap ownership.
- Create a decision record for the Spirit composition boundary and renderer/security approach.

### Phase 1: Community Shell And Forum UX Foundation

- Rename the product to “Спільнота” across main-site and forum navigation/metadata.
- Establish shared visual tokens and a modern responsive forum shell.
- Redesign `/forum/` as the community home with publication and discussion sections, initially allowing publication placeholders if necessary.
- Improve discussion listing/detail/create/reply screens without changing their underlying behavior.
- Add prefix-routing and core forum smoke tests before deeper model changes.

### Phase 2: Publication Domain And Workflow

- Add the local publication app, migrations, permissions, service layer, and administrative/editor surfaces.
- Implement draft creation, editing, preview, submission, review, changes requested, rejection, publication, and archival.
- Define transactional behavior between publication metadata, Spirit topic, and body/comment creation.
- Add cover upload and metadata validation.
- Implement author dashboard and editor review queue.
- Ensure search and anonymous visibility respect publication status.

### Phase 3: Publication Presentation And Comments

- Add publication listing and article layouts.
- Reuse Spirit replies as article comments with correct authorization and canonical navigation.
- Add author/type/editorial labels, dates, related content, empty states, and responsive presentation.
- Resolve generic topic URL behavior for publication-backed topics.

### Phase 4: SEO, Sitemaps, And Launch Hardening

- Add canonical/social/structured metadata.
- Add publication sitemap and integrate it with the root sitemap discovery strategy.
- Add robots/indexability tests and verify anonymous production-like responses.
- Complete accessibility, mobile, performance, upload, moderation, and security verification.
- Record rollout, monitoring, rollback, and known limitations.

## Risks And Unknowns

- Spirit is not designed as a typed-content CMS; assumptions about the first comment may be brittle.
- Spirit's old Markdown dependency is an existing security and maintenance risk that becomes more important with long-form public submissions.
- The forum and core use different databases, so catalog relationships and user identity must not assume cross-database foreign keys or perfectly synchronized profiles.
- Prefix handling can fail subtly in redirects, canonical URLs, static/media paths, OAuth `next` values, sitemap generation, and client-side requests.
- Overriding many Spirit templates may create an expensive compatibility layer during package upgrades.
- Spirit search may index drafts or duplicate topic content unless explicitly controlled.
- Comment activity currently affects `Topic.last_active`; that must not incorrectly change publication `lastmod` or editorial ordering.
- Editing/deleting the first comment may damage the article body if ownership is not enforced.
- Existing translations and terminology may be incomplete after renaming.
- Low initial activity makes empty-state and company-seeded content quality important.
- Moderation and medical/veterinary claims need policy, not only technical controls.

## Test Strategy

### Routing And Deployment

- `/forum` redirects to `/forum/`.
- All reverse-generated public forum, publication, auth, static, media, sitemap, pagination, and AJAX URLs include `/forum` externally.
- OIDC login, callback, logout, and `next` return paths survive the proxy prefix.
- No intended forum page is publicly exposed through an unprefixed main-site route.

### Publication Domain

- State-transition unit tests cover all allowed and forbidden transitions.
- Author, editor, moderator, administrator, anonymous, and unrelated-user authorization tests cover every action.
- Draft/private states never appear in anonymous lists, search, comments, feeds, or sitemaps.
- Topic/body/metadata creation and failure behavior do not leave inconsistent orphan records.
- Slug changes and canonical redirects behave according to the chosen policy.
- Published edits follow the chosen re-review policy.

### Spirit Compatibility

- Existing forum home, categories, topic detail, topic publishing, replies, edits, likes, flags, polls, notifications, unread state, private messages/topics, search, profile, and admin smoke tests continue to pass.
- Publication comments correctly use Spirit reply, notification, flag, and moderation behavior.
- Publication-backed topic redirects/canonicals do not break comment permalinks or notification links.

### Content Security

- Markdown/HTML regression cases cover raw HTML, unsafe schemes, encoded/malformed URLs, images, links, nesting, and stored-content rendering.
- Upload tests cover content type, extension mismatch, size, dimensions, authorization, storage, replacement, deletion, and missing files.
- CSRF, object authorization, rate limits, and unpublished-content leakage receive targeted tests.

### SEO

- Only eligible publications appear in the publication sitemap.
- `lastmod`, canonical, robots, Open Graph, and structured-data values are correct.
- Generic backing topic pages do not create indexable duplicates.
- Sitemap URLs resolve anonymously through Nginx at their `/forum/` paths.

### Visual And Accessibility

- Verify community home, publication listing/detail/create/edit/review, discussion listing/detail/create/reply, search, profile, notifications, and important moderation screens.
- Test authenticated and anonymous states, empty and populated states, validation errors, long Ukrainian content, missing images, and narrow/mobile layouts.
- Run keyboard and basic automated accessibility checks plus manual heading, landmark, focus, label, contrast, and responsive review.

### Commands

Prefer the repository's Docker Compose workflow:

```bash
just ps
just forum-test
just test
just collectstatic
```

Add focused forum test commands as the new app grows, and run both services' checks whenever shared navigation, OIDC, proxy assumptions, or sitemap integration changes.

## Rollout And Recovery

- Introduce additive tables and routes before changing existing discussion behavior.
- Preserve a reversible navigation flag or deployment switch until the new community home and publication workflow are verified.
- Seed initial company-authored publications before or alongside launch so empty states are not the default public experience.
- Keep old forum topic URLs functional and prepare explicit redirects only for deliberately changed public paths.
- Record migration counts, status counts, sitemap URL counts, and anonymous smoke results in `docs/work/results/`.
- Define rollback behavior for publication routes and navigation without deleting submitted drafts or backing topics.
- Monitor 404s, redirect loops, 5xx responses, failed uploads, moderation backlog, sitemap fetches, and duplicate/incorrect canonical signals after rollout.

## Documentation Updates

- Add a business-domain note for community content, actors, publication types, lifecycle, moderation, and editorial rules.
- Add an engineering decision for the Spirit composition boundary, body ownership, renderer/security path, and `/forum/` URL invariant.
- Update forum README and deployment documentation with new routes, permissions, sitemap ownership, and proxy assumptions.
- Update main-site navigation/SEO documentation where sitemap discovery changes.
- Write a result artifact with migrations, verification evidence, remaining risks, and rollback notes.

## Implementation Checklist

- [x] Confirm the plan in the new implementation task and mark it In Progress.
- [x] Read both projects' current instructions and preserve unrelated changes.
- [x] Complete Phase 0 investigation and record the required decisions.
- [ ] Confirm production `/forum/` proxy behavior and add prefix regression tests.
- [x] Define publication body ownership, slug policy, permissions, and published-edit rules.
- [x] Define and document the Markdown/rendering security path.
- [ ] Implement the community shell and rename visible forum navigation.
- [ ] Redesign existing forum discovery, topic, reply, search, profile, and mobile views.
- [ ] Add the publication companion model, migrations, lifecycle, and service layer.
- [ ] Add authoring, preview, author dashboard, and editor review workflows.
- [ ] Add publication listing/detail layouts and Spirit-backed comments.
- [ ] Prevent duplicate generic-topic indexing for publication-backed topics.
- [ ] Add publication metadata, canonical tags, structured data, and sitemap.
- [ ] Integrate forum sitemap discovery with the main site.
- [ ] Run forum, main-site, proxy, security, SEO, visual, mobile, and accessibility verification.
- [ ] Seed or prepare initial company publications.
- [ ] Update durable business and engineering documentation.
- [ ] Write the result and rollout/rollback record.

## Starting Prompt For The New Task

Use the following request in the new task:

> Implement the AgroMega Community, Publications, and Forum Redesign plan in `docs/work/plans/2026-07-11-community-publications-and-forum-redesign.md`. Start with Phase 0, inspect both `am-core` and the sibling `forum_instance`, confirm the `/forum/` Nginx proxy invariant, and record the required architecture/security decisions before implementation. Keep all public community and publication URLs under `/forum/`, compose around Spirit rather than modifying its installed models, and seriously redesign the existing forum experience as part of the work.
