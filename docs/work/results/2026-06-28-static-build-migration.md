# Result: Static Build Migration

- Date: 2026-06-28
- Plan: `docs/work/plans/2026-06-28-static-build-migration.md`

## Summary

Custom Django static source assets from `am-front/src` now live in `am-core/frontend/src`.

`am-core/frontend` contains the npm/webpack build workflow for Django-owned SCSS and JavaScript. The build writes to `core/posts/static/posts/`, preserving existing template static paths such as `posts/main.css`, `posts/list.css`, `posts/j-index.js`, `posts/j-detail.js`, and `posts/j-gallery.js`.

The old `node-sass` dependency was not carried forward. The new workflow uses Dart Sass through the maintained `sass` package.

The parent `am-dev/docker-compose.yml` no longer defines the `front` service, and parent `am-dev/.gitmodules` no longer registers `am-front`.

Follow-up cleanup removed the parent `am-front` submodule index entry, deleted the local `../am-front` working tree and `.git/modules/am-front` metadata, removed stale `am-front` Docker containers, and confirmed legacy non-post static paths are resolved from installed Django packages or `am-core` static directories.

## Verification

- `npm --prefix frontend install`: passed and generated `frontend/package-lock.json`.
- `npm --prefix frontend audit --audit-level=moderate`: initially found a vulnerable `css-minimizer-webpack-plugin` transitive dependency; after upgrading to `css-minimizer-webpack-plugin@^8.0.0`, npm reported `found 0 vulnerabilities`.
- `npm --prefix frontend run build:static`: passed and regenerated the Django static outputs.
- `just check`: passed; existing warnings remain for unsupported CKEditor 4 and non-unique `User.email` as `USERNAME_FIELD`.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev build core`: passed after adding `nodejs` and `npm`.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev run --rm --no-deps core npm --prefix frontend run build:static`: passed inside the rebuilt core image; legacy Sass deprecation warnings remain.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev run --rm --no-deps core ./manage.py findstatic ... --settings=settings.dev`: confirmed CKEditor, autocomplete-light, mptt, silk, PWA icons, manifest, service worker, robots, and comment static assets resolve without `am-front`.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev run --rm --no-deps core ./manage.py collectstatic --noinput -i node_modules --settings=settings.dev`: passed, copying 3246 static files with 357 unmodified.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev run --rm --no-deps core ./manage.py check --settings=settings.test_settings`: passed; existing warnings remain for unsupported CKEditor 4 and non-unique `User.email` as `USERNAME_FIELD`.

## Known Follow-Ups

- The Sass build emits deprecation warnings for legacy `@import` usage and `quote()`. This is not blocking today, but the SCSS should be migrated to the Sass module system before Dart Sass 3.0.0.
- The parent `am-dev` repo still had unrelated pre-existing local changes around `forum_instance`; those were preserved.
