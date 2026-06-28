# Plan: Static Build Migration

- Date: 2026-06-28
- Status: Implemented
- Owner: Andrii / Codex
- Related domain: Site frontend assets
- Related decisions: 2026-06-21 knowledge base and planning workflow

## Goal

Move ownership of custom Django static source assets from the legacy `am-front` project into `am-core`, add a maintained static asset build workflow inside `am-core`, and make the local stack work without the `am-front` service or submodule.

## Non-Goals

- Redesigning templates or changing product UI behavior.
- Replacing all legacy JavaScript patterns in the same step.
- Moving forum-owned static assets into `am-core`.
- Removing third-party Django app static assets that are already supplied by installed Python packages.

## Current Understanding

- `../docker-compose.yml` still defines a `front` service that builds `./am-front`, mounts it at `/app`, and shares the `am-static` volume.
- `../.gitmodules` still registers `am-front` as a submodule.
- `am-front` owns source files under `src/scss/` and `src/js/`, while `am-core` already contains compiled `core/posts/static/posts/*.css` and `j-*.js` outputs used by Django templates.
- The legacy build uses webpack 5 and `node-sass`. `node-sass` should be replaced with the maintained Dart Sass implementation through the `sass` package.
- `am-core` uses Django `collectstatic` into the shared `/static` volume for local Docker, and nginx serves that volume.

## Assumptions

- The first migration should preserve current static URLs such as `posts/main.css`, `posts/j-index.js`, and related font/image outputs.
- Source SCSS and JavaScript should live in `am-core` so future Django template changes and static overrides can be changed together.
- The local Docker image can install Node.js tooling only when needed for asset builds, while Python dependencies remain managed by uv.
- The forum project keeps its own static pipeline and continues collecting into the shared `am-static` volume.

## Proposed Approach

1. Add an `am-core` frontend workspace for Django-owned static sources and build configuration.
2. Copy the legacy custom SCSS, JavaScript, and referenced source fonts/images from `am-front/src` into that workspace.
3. Add `package.json` scripts for `build:static` and `watch:static`, using webpack with Dart Sass.
4. Configure webpack output to `core/posts/static/posts/` so existing Django template `{% static %}` paths keep working.
5. Update ignore rules so local Node dependencies stay untracked and compiled Django static outputs remain under intentional source control where they are already tracked.
6. Add `just` helpers that run the static build inside the core container.
7. Remove the `front` service from the parent Docker Compose stack and remove the `am-front` submodule registration from the parent repo.

## Risks And Unknowns

- Rebuilding may change minified CSS/JS bytes even when behavior is unchanged, especially after replacing `node-sass`.
- The legacy source may not fully cover all files currently served from `am-front/static`, so non-post assets such as CKEditor, autocomplete, mptt, favicon, and root PWA files need an asset inventory before deleting `am-front`.
- Parent `am-dev` repository edits are outside the `am-core` writable root and need explicit approval in this Codex session.
- Local Docker image size may grow if Node.js is installed in the main core image. A later optimization could use a separate build stage.

## Test Strategy

- Run `npm install` or `npm ci` for the new `am-core` static workspace.
- Run the static build and verify expected outputs exist under `core/posts/static/posts/`.
- Run `just collectstatic` so Django collects the assets into the shared volume.
- Run `just check` or the closest available Django system check.
- Smoke test pages that load `posts/main.css`, `posts/list.css`, `posts/detail.css`, `posts/j-index.js`, `posts/j-detail.js`, and `posts/j-gallery.js`.

## Documentation Updates

- Keep this plan updated as the migration proceeds.
- Add a result artifact under `docs/work/results/` after implementation and verification.
- Add a durable engineering note if the static build workflow becomes the accepted replacement for `am-front`.

## Implementation Checklist

- [x] Confirm the custom source asset inventory from `am-front/src`.
- [x] Add the `am-core` static source workspace and build scripts.
- [x] Build static assets from `am-core`.
- [x] Update Docker/just workflow for local static builds.
- [x] Remove `am-front` from parent Docker Compose and submodule metadata.
- [x] Run targeted build and npm audit verification.
- [x] Write result artifact with remaining follow-ups.
