# Result: Token-authenticated content API

- Date: 2026-07-11
- Status: Complete
- Related plan: `docs/work/plans/2026-07-11-token-content-api.md`

## Delivered Contract

All endpoints require `Authorization: Token <key>` and reject session-only or anonymous access.

- `GET /api/content/categories/tree/` returns the complete active category hierarchy. Every node contains `id`, `slug`, `title`, and `children`.
- `GET /api/content/countries/` returns `id`, `slug`, `short_slug`, and `title` for every country.
- `GET /api/content/posts/` returns detailed posts ordered newest database ID first. It supports `rubric=<id-or-slug>`, `country=<id-or-slug-or-short-slug>`, `page=<number>`, and `page_size=<1-100>`.
- `POST /api/content/posts/` requires `title`, `text`, and `rubric`. Optional writable fields are `work_status`, `author`, `source`, `sources`, `status`, `country`, `meta_description`, and `category_attributes`. The publisher is always the token owner.
- `GET`, `PUT`, or `PATCH /api/content/posts/<id>/` retrieves or updates a post owned by the token user. Another user's post returns `404` and the publisher cannot be changed through the request body.

Post responses include IDs and editorial fields plus nested rubric/country summaries, tag names, category attributes, photos, counters, timestamps, publication state, slug, and URL.

## Verification

- `just test-target api.v1.content`: 8 tests passed.
- `just flake`: passed.
- `git diff --check`: passed.

The test run reported the repository's existing CKEditor security warning and non-unique email system-check warning; neither was introduced by this change.
