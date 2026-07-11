# Plan: Sheep Breed Catalog Content Refresh

- Date: 2026-07-11
- Status: Draft
- Owner: Content operations / engineering
- Related domain: Catalog information
- Related decisions: Token-authenticated content API

## Goal

Replace poor legacy machine translations in the sheep-breed rubric (`955`) with accurate, useful Ukrainian catalog articles while preserving post identity, URLs, ownership, publication state, media, and unrelated metadata.

## Non-Goals

- Do not publish unreviewed generated text directly to all posts.
- Do not change post IDs, slugs, rubrics, publishers, dates, counters, photos, or tags.
- Do not claim breed measurements, production figures, health traits, or conservation status without source support.
- Do not copy source prose or images.

## Current Understanding

- `GET /api/content/posts/?rubric=955&page_size=100` can export the rubric in three pages if it contains about 226 posts.
- `PATCH /api/content/posts/<id>/` can update `title`, `text`, `author`, `source`, `sources`, `status`, `country`, `meta_description`, and category attributes.
- Updates require a token-authenticated staff user. The staff editor can update posts across publishers while the API preserves each original publisher.
- `Post.text` and `Post.sources` are CKEditor rich-text fields and accept HTML.
- The current API has no revision record, editorial review state, conditional update, bulk endpoint, or explicit idempotency key.

## Assumptions

- Ukrainian is the target publication language.
- Existing titles identify real sheep breeds, though some will require alias/transliteration resolution.
- FAO DAD-IS is the preferred global identity/reference source; national breed societies, government registries, universities, and peer-reviewed sources can supplement it.
- A human editor will approve uncertain matches and a pilot batch before full publication.

## Proposed Approach

### 1. Inventory and ownership audit

Create a resumable management command or external worker that calls the content API and stores a JSONL manifest containing the API response, post ID, original-content checksum, and fetched timestamp. Report:

- total posts and pagination completeness;
- publisher IDs and how many are writable by the token;
- duplicate or suspicious titles;
- empty/missing country, sources, and metadata;
- existing HTML quality and likely language;
- posts that may not describe a sheep breed.

No update is allowed in this stage.

### 2. Breed identity resolution

For each post, derive a normalized breed identity with aliases in Ukrainian, English, and the native language where known. Resolve it against authoritative sources and record:

- canonical name and aliases;
- country/region of origin;
- production purpose (wool, meat, dairy, multi-purpose, hair sheep, etc.);
- source URLs and access date;
- match confidence and an explanation;
- conflicts between sources.

Low-confidence, ambiguous, composite, extinct, or duplicate entries go to a manual-review queue rather than generation.

### 3. Evidence packet

Store a compact, structured evidence packet per post. Every factual field must point to at least one source. Prefer this source order:

1. FAO DAD-IS / EFABIS or a national government breed registry;
2. official breed society or agricultural university extension;
3. peer-reviewed or reputable institutional publication;
4. the existing article only for facts independently verified elsewhere.

Search snippets, Wikipedia, commercial farms, and generic breed-list sites may help find aliases but should not be the sole authority for factual claims.

### 4. Generate constrained Ukrainian content

Generate from the evidence packet, not directly from web pages. Use a fixed CKEditor-compatible fragment:

```html
<p>Короткий вступ із визначенням породи та її походженням.</p>
<h2>Походження та поширення</h2>
<p>...</p>
<h2>Напрям продуктивності</h2>
<p>...</p>
<h2>Зовнішні ознаки</h2>
<p>...</p>
<h2>Утримання та використання</h2>
<p>...</p>
<h2>Переваги та обмеження</h2>
<ul><li>...</li></ul>
```

Only use simple semantic HTML supported by CKEditor (`p`, `h2`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, and safe `a` links). Do not add inline styles, scripts, copied images, invented quotations, or unsupported numeric ranges. Omit a section when evidence is insufficient. Keep sources in the API `sources` field and produce a factual `meta_description` within 250 characters.

### 5. Automated quality gates

Reject candidates that fail any of these checks:

- unexpected language or obvious translation artifacts;
- unsupported numbers or claims absent from the evidence packet;
- unsafe/disallowed HTML;
- title/breed mismatch;
- missing source provenance;
- duplicate content above a similarity threshold;
- meta description over 250 characters;
- accidental changes to protected fields;
- content substantially shorter or less informative than the approved template minimum.

### 6. Review artifacts and pilot

Produce a review bundle (CSV/JSONL plus rendered before/after HTML) containing the proposed patch and diff. Manually review all low-confidence items and a representative high-confidence sample. Then publish only 5-10 approved posts as a pilot.

Verify public rendering, links, mobile layout, indexing metadata, API output, and update dates. Keep the pilot observable for at least one editorial review cycle before expanding.

### 7. Safe publication

Before each `PATCH`:

- fetch the post again;
- compare its current checksum with the inventory checksum;
- skip it if a person or another process changed it;
- save the full original response in a rollback artifact;
- patch only approved mutable fields;
- fetch again and verify the stored result.

Run in small batches (for example 10-20), with rate limiting, retries only for safe transient failures, a persistent per-post state machine, and a stop threshold for validation/API errors. Never retry a conflicting or rejected update automatically.

### 8. Rollback and audit

The run ledger should record post ID, source URLs, model/prompt version, evidence checksum, old/new content checksums, reviewer, approval time, API response, and verification result. A rollback command should restore the exact saved mutable fields, again guarded by a checksum so it cannot overwrite later human edits.

## Required API/Workflow Decisions

1. Create a dedicated active staff integration user and token for the refresh. Store the token only in the runtime environment, rotate/revoke it after the campaign, and do not grant superuser status.
2. Decide whether updates remain published immediately (`status=true`) or whether an editorial draft/review state must be introduced first.
3. Decide whether titles may be corrected or only article text, sources, country, and metadata.
4. Confirm Ukrainian editorial style, target article length, and whether husbandry advice should be general or localized for Ukraine.
5. Decide whether authoritative external links should be visible in the article or only stored in `sources`.

## Risks And Unknowns

- A compromised staff token can edit the full post catalog, so its storage, logging, lifetime, and rotation require care.
- Breed names may be mistranslated aliases, causing incorrect source matching.
- Source facts can vary by country population or breed line; values must not be merged as if universal.
- A purely generative pipeline can create plausible but false livestock information.
- Updating `update_date` on all posts may affect sitemaps, SEO, and user expectations.
- CKEditor 4 is already documented as unsupported and should receive only sanitized, conservative HTML.
- External source terms may permit factual use but not wholesale copying or image reuse.

## Test Strategy

- Unit tests for pagination, checkpointing, normalization, evidence validation, HTML sanitization, checksums, and protected-field enforcement.
- API contract tests for owner/non-owner updates and changed-since-inventory conflicts.
- Fixture tests for aliases, ambiguous breeds, missing sources, Unicode Ukrainian text, and malformed legacy HTML.
- Dry run over all rubric `955` posts with zero PATCH requests.
- Pilot update and rollback in a non-production environment, followed by 5-10 reviewed production posts.
- Public-page visual checks and post-update API readback.

## Documentation Updates

- Record the final editorial rules and ownership decision in the catalog-information domain note.
- Store inventory, pilot, publication, and rollback verification under `docs/work/results/` without secrets or full copyrighted source text.

## Implementation Checklist

- [ ] Confirm production API base URL and provide a dedicated staff token through an environment variable or secret store.
- [ ] Audit rubric `955` count and ownership with a read-only export.
- [ ] Approve source policy, Ukrainian style guide, and editable fields.
- [ ] Implement the resumable inventory/enrichment/review/publish worker.
- [ ] Add automated quality and concurrency guards.
- [ ] Run and approve a full dry-run report.
- [ ] Publish and verify a 5-10 post pilot.
- [ ] Process remaining approved posts in monitored batches.
- [ ] Store the result/rollback audit and update domain documentation.
