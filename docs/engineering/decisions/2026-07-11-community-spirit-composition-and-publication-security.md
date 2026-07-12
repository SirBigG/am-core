# Decision: Community Spirit Composition And Publication Security

## Amendment: direct publishing and inline media (2026-07-11)

Authenticated members publish and update their own publications immediately after accepting the versioned community content policy. The publication records the acceptance timestamp and policy version. Authors remain responsible for legality, accuracy, disclosures, and third-party rights; AgroMega retains authority to hide, archive, or remove content. Inline editor images use authenticated, validated uploads, and the separate cover field is retired. This amendment replaces the pre-publication review and review-required edit rules below where they conflict.

## Amendment: canonical community namespace (2026-07-12)

The public namespace changes from `/forum/` to `/community/`. Nginx permanently redirects the legacy path, including nested routes, to the equivalent canonical path. Proxy script-name handling, generated URLs, authentication returns, assets, media, sitemap discovery, and OIDC callbacks use exactly one `/community` prefix. This amendment supersedes the `/forum/` URL invariant below while retaining its security and prefix-preservation requirements.

- Date: 2026-07-11
- Status: Accepted
- Owners: AgroMega engineering

## Context

AgroMega is adding moderated long-form publications to the separately deployed Spirit forum. Spirit remains useful for identities synchronized through OIDC, discussion topics, replies, notifications, likes, flags, and moderation, but its models do not own the publication lifecycle or editorial metadata. Its legacy Markdown stack is also not a suitable dependency to expand for new long-form content.

The forum is publicly mounted below `/forum/`. Nginx strips that prefix before proxying and supplies the script-name context used by Django. Losing the prefix in a redirect, form, asset, canonical URL, sitemap, or authentication return target would expose a broken or unsafe public contract.

## Decision

### Composition and ownership

- Keep `am-core` and `forum_instance` as separate applications and databases. AgroMega remains the OIDC provider.
- Add publication state to an AgroMega-owned app in `forum_instance`; do not change Spirit package source or add fields to Spirit-owned models.
- A publication has a one-to-one backing Spirit topic so replies, notifications, flags, and existing moderation continue to work.
- The publication model owns the article body explicitly. The first Spirit comment is not the authoritative publication body. It may be created as a compatibility marker or synchronized excerpt only if tests prove that doing so cannot expose drafts, create duplicate indexing, or allow Spirit editing/deletion to alter the article.
- Cross-service references use stable typed identifiers or validated URLs, never database foreign keys to `am-core`.

### Rendering and content security

- Publication bodies use an independent, maintained Markdown rendering and sanitization path owned by the publication app. New publication rendering must not call Spirit's Mistune 0.8.4 internals.
- Raw HTML and unsafe URL schemes are rejected or removed. Scripts, iframes, remote forms, and arbitrary embeds are not allowed.
- Renderer regression tests cover encoded and malformed links, images, nesting, unsafe schemes, and stored-content output. Cover uploads require type and content agreement, size and dimension limits, safe storage names, and object-level replacement/deletion authorization.
- Existing Spirit discussion rendering remains unchanged initially and its legacy risk remains separately tracked; publication launch does not imply that risk is accepted for new content.

### Lifecycle, URLs, and permissions

- Published edits by an author create a new review-required revision or return the publication to review; authors cannot silently replace public content. Explicitly authorized editors may correct and republish through an audited service action.
- The canonical publication slug is assigned once and is immutable. Title edits do not change the public URL. A later exceptional slug correction requires an explicit permanent redirect record.
- Direct publication and review actions require an explicit Django permission such as `community.review_publication`/`community.publish_publication`; staff status, username, category membership, or company naming alone is insufficient.
- Every draft, preview, edit, submit, review, publish, reject, archive, upload, and comment action enforces object-level authorization. Non-published states are absent from anonymous pages, search, feeds, comments, and sitemaps.

### Proxy, authentication, and SEO

- `/forum/` is an external URL invariant for all community pages, redirects, form actions, pagination, JavaScript requests, static/media assets, canonical and social metadata, sitemaps, and OIDC callbacks.
- Authentication `next`/return values must be local, normalized, and constrained to the `/forum/` namespace before redirect. Host, scheme-relative, encoded, or prefix-escaping targets are rejected. Proxy-aware absolute URLs rely only on configured forwarded host/protocol handling.
- `forum_instance` owns a publication sitemap below `/forum/` and derives `lastmod` from meaningful publication updates, not comment activity. `am-core` discovers it from the root sitemap index. Only canonical, published, anonymously accessible publications are included.
- A publication-backed generic Spirit topic resolves to the canonical publication URL, or is `noindex` with that canonical where a redirect would break comment permalinks. It must never be a second indexable article page.

## Consequences

Publication behavior remains insulated from Spirit upgrades and model assumptions, while established discussion capabilities can be reused. Explicit body ownership makes draft isolation, revision review, rendering, and meaningful update timestamps reliable. Immutable slugs make canonical URLs stable.

The forum app now owns an additional renderer, sanitizer, revision workflow, permissions, and sitemap. Topic and publication creation must be coordinated by a service layer with cleanup or recovery for partial failure because the relationship spans multiple owned tables. Existing Spirit Markdown still requires a separate upgrade or mitigation plan.

## Alternatives Considered

- Making the first Spirit comment authoritative was rejected because deletion, edits, moderation, indexing, and package behavior make the publication body lifecycle brittle.
- Reusing Spirit's legacy renderer was rejected because it deepens dependence on an obsolete parser for a larger public attack surface.
- Mutable title-derived slugs were rejected because they require pervasive redirects and make shared links unstable.
- Allowing staff or named accounts to publish implicitly was rejected because it obscures authorization and audit intent.
- Serving publication URLs or data from `am-core` was rejected because it duplicates ownership and violates the existing deployment boundary.

## Follow-Up

- Implement the companion model, revision/service layer, explicit permissions, independent renderer, upload validation, and security regression tests.
- Add prefix and safe-return-path tests through a production-like Nginx route.
- Verify the production proxy headers and sitemap discovery configuration before launch.
- Record the remaining Spirit discussion-renderer risk and its remediation timeline before production publication launch.
