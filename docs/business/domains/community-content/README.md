# Domain: Community Content

## Direct-publishing policy amendment (2026-07-11)

Authenticated members may publish and update their own publications immediately after accepting the current community content policy. Authors are responsible for legality, factual claims, disclosures, and rights to submitted text and media. Hosting does not mean AgroMega endorses a user publication. AgroMega may restrict, hide, archive, or remove content or accounts when material violates community rules, law, safety expectations, or third-party rights. Images are optional inline editor blocks; publications do not use a separate cover field. This amendment replaces the review-first rules below where they conflict.

## Public namespace amendment (2026-07-12)

The canonical public namespace for **Спільнота AgroMega** is `/community/`. Existing `/forum/` links permanently redirect to their equivalent `/community/` destinations so shared links and search history remain usable. The internal service and code may retain the `forum` name; the public product URL does not.

## Purpose

**Спільнота AgroMega** gives agricultural users one coherent place for durable, moderated publications and conversational discussions. Publications capture guides, selections, expert material, company editorial content, and personal experience; discussions retain the faster forum workflow.

## Actors

- Visitor: reads published public content and eligible discussions.
- Member: an authenticated AgroMega user synchronized to the forum through OIDC; creates discussions and publication drafts and comments where allowed.
- Author: owns and revises a publication submission.
- Editor: reviews submissions, requests changes, rejects, publishes, corrects, features, or archives content under explicit permissions.
- Moderator: applies the existing discussion/comment flagging and moderation rules.
- Company or trusted contributor: may receive explicit direct-publishing permission; identity or company affiliation alone grants no editorial power.
- Administrator: assigns permissions and operates recovery procedures.

## Core Workflows

1. A member creates and previews a publication draft, including its type, summary, body, cover, alternative text, and disclosures.
2. The author submits it for review. An editor publishes it, requests changes, or rejects it with a private editorial note.
3. A published article has one canonical page. Members discuss it through Spirit-backed replies shown as comments.
4. Author changes to published material require renewed review; editorial corrections are explicit and audited.
5. Editors may archive content without destroying its submission and audit history.
6. Members continue creating and replying to ordinary discussions without the publication workflow.

## Business Rules

- User publications require approval before anonymous discovery. Direct publishing is an explicit permission.
- Drafts, previews, review submissions, changes-requested items, rejected items, and archived items are private to authorized actors and excluded from search, feeds, comments, and sitemaps.
- Editorial notes and status history are never public.
- Publication types initially are guide, ranking/selection, expert article, personal experience, and company editorial.
- Commercial or sponsored relationships require a visible disclosure label.
- Cover images require meaningful alternative text unless they are explicitly decorative.
- Publication URLs remain stable when titles change. The article, not its backing discussion topic, is the canonical search result.
- Replies are allowed only after publication and follow existing Spirit flagging and moderation rules.
- Veterinary, medical, sponsored, and other sensitive claims require editorial policy and review; technical sanitization alone is not approval.

## States And Lifecycle

```text
draft -> in_review -> published
                  -> changes_requested -> draft
                  -> rejected
published -> in_review -> published
published -> archived
```

Authors edit `draft` and `changes_requested` content. Submitting transfers it to editorial review. Published author edits return to review rather than silently replacing the public version. Archived content is not anonymously discoverable; restoration requires an explicit editorial action.

## Neighboring Domains

- Authentication and identity: `am-core` owns identity; the forum owns its synchronized local user and session.
- Catalog information and companies: publications may reference stable public identifiers or URLs, but no cross-database foreign keys are permitted.
- News and editorial content: company publications may share editorial standards, while their lifecycle and canonical page remain forum-owned.
- Search and SEO: the forum determines publication eligibility and sitemap timestamps; the main site exposes forum sitemap discovery.

## Implementation Map

- `forum_instance`: community/publication models, workflow, rendering, uploads, permissions, pages, comments, sitemap, and moderation integration.
- Spirit: backing topics, replies, users, notifications, likes, flags, and existing discussion behavior.
- `am-core`: OIDC identity, main navigation label, and root sitemap discovery.
- Nginx: the public routing boundary is `/community/`, with compatibility redirects from `/forum/`.

## Open Questions

- Which roles receive review, publish, feature, archive, and direct-publish permissions at launch?
- What editorial response-time target and escalation policy apply to the review queue?
- Which claim categories require specialist review or standardized disclaimers?
- Which public discussions, if any, meet the quality threshold for sitemap inclusion?
- What retention and appeal policy applies to rejected and archived submissions?
