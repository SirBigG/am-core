# SEO And Homepage Performance Baseline Result

- Date: 2026-07-11
- Plan: `docs/work/plans/2026-07-11-seo-performance-baseline.md`

## Delivered

- Every base-template page now emits one self-referencing canonical URL using the configured public host and current path without query parameters.
- `/search/` and every query-string variant emit `noindex,follow`; clean URLs emit `index,follow` unless a page keeps a stricter explicit policy.
- The main sitemap now normalizes the public host, includes `https://agromega.in.ua/` once, and deduplicates all generated locations.
- The large shared and homepage inline style blocks moved into the existing frontend build as `site.css` and `index.css`.
- The homepage hero background is preloaded at high priority. Content images use lazy loading and async decoding; imgproxy-backed event and post images also expose `srcset` and `sizes`.
- Static S3 objects use `public, max-age=31536000, immutable`; media retains its separate shorter policy.
- Production static URLs include the configured `MEDIA_VERSION`, preventing immutable browser caches from serving a previous deployment's CSS or JavaScript.
- The service worker uses network-first loading for CSS and JavaScript and cache version `agromega-v2`, so local development no longer serves an older stylesheet before checking the network.

## Verification

- `just static-build`: passed. Existing Sass and Bootstrap deprecation warnings remain.
- Focused Django run covering homepage metadata, search metadata, sitemap uniqueness, and live storage settings: 16 tests passed.
- `git diff --check`: passed after final whitespace cleanup.

## Operational Note

Existing static objects need to be republished/collected during deployment for the new cache metadata and newly generated `site.css` to reach storage.
