# AgroMega Core

AgroMega Django backend and API project. The forum instance is a sibling
project in the parent `am-dev/forum_instance/` folder and runs as a separate
Django service.

## Local Development

The project is normally run from the parent `am-dev` folder with Docker Compose.

Compose file:

```text
/Users/andriihots/Projects/am-dev/docker-compose.yml
```

Common commands from this `am-core` folder:

```bash
just start
just ps
just check-deps
just test
just test-target core.adverts
just migrate
just static-install
just static-build
just collectstatic
just forum-test
```

Nginx exposes the local app on port `8000`. The compose setup mounts this repo
into the `core` container at `/am-core` and mounts the sibling
`../forum_instance/` project into the forum container at `/app`.

## Static Assets

The old `am-front` project is retired. Custom Django-owned SCSS and JavaScript
now live in `frontend/src/` and build into existing Django static paths under
`core/posts/static/posts/`.

Typical workflow:

```bash
just static-install
just static-build
just collectstatic
```

Use `just static-watch` while editing frontend source files. Frontend build
dependencies are tracked in `frontend/package.json` and
`frontend/package-lock.json`; Python dependencies remain managed by uv.

Third-party Django package static assets such as CKEditor, autocomplete-light,
mptt, silk, and comment assets are supplied by installed Python packages. PWA
root files such as icons, manifest, and service worker live in `pwa/`.

## Documentation

Project docs live under `docs/`:

- `docs/engineering/` for technical plans, architecture notes, investigations,
  upgrade reports, and implementation records.
- `docs/business/` for product, domain, operations, content, and other future
  business documentation.

Current package upgrade and test plan:

- `docs/engineering/package-upgrades/2026-05-11-package-upgrade-test-plan.md`
- `docs/engineering/testing/README.md`

Agent-specific project memory lives in `AGENTS.md`.
