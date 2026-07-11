# SEO And Indexing Hardening Result

- Date: 2026-07-11
- Plan: `docs/work/plans/2026-07-11-seo-indexing-hardening.md`

## Outcome

- Canonical and Open Graph URLs now share the configured, normalized public origin.
- Authentication, account, feedback, search, and content-creation routes emit `noindex,follow`.
- Query-string variants remain `noindex,follow` and canonicalize to the clean path.
- The sitemap index works without published posts or active adverts.
- Sitemap index `lastmod` values render when actual local data exists.
- The remote news sitemap no longer receives a fabricated current-time modification date.
- Main, advert, and sitemap-index URLs tolerate a trailing slash in `HOST` without producing double slashes.
- Advert sitemap retention behavior remains unchanged.

## Verification

- `just test-target core.posts`: 65 tests passed.
- `just test-target core.adverts`: 28 tests passed.
- `just flake`: passed.
- `git diff --check`: passed.

Existing Django system-check warnings about CKEditor 4 and non-unique login email remain outside this change. Existing test warnings about naive fixture datetimes and unordered gallery pagination also remain.

## Follow-Up

Structured data and a product-level policy for independently indexable filtered landing pages remain separate improvements. They need content-specific schema and indexation decisions rather than a mechanical global rule.
