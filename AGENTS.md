# AGENTS.md

Guidance for Codex and other coding agents working in this repository.

## Project Context

This repo is the `am-core` Django backend for AgroMega. It is usually run locally from the parent `am-dev` folder, not from this folder alone.

Local Docker Compose config:

- Compose file: `../docker-compose.yml`
- Main service: `core`
- Forum service: `forum_instance`
- Database service: `db`
- Nginx service exposes local port `8000`
- The compose file mounts this repo as `./am-core:/am-core`
- The forum project lives outside this repo at `../forum_instance` and is mounted as `./forum_instance:/app`
- The legacy `am-front` service/submodule is retired. Do not add new work there.

Useful local commands from this `am-core` folder:

```bash
just ps
just start
just test
just test-target core.adverts
just test-api
just flake
just migrate
just static-install
just static-build
just collectstatic
just forum-test
```

## Static Asset Workflow

Custom Django-owned SCSS and JavaScript live in `frontend/src/` and build into Django app static files under `core/posts/static/posts/`.

Use the local Docker workflow:

```bash
just static-install
just static-build
just collectstatic
```

For active SCSS/JavaScript work:

```bash
just static-watch
```

Important static asset rules:

- Keep custom frontend source in `frontend/src/`.
- Keep compiled outputs at the existing Django static paths unless templates are intentionally changed.
- Use Dart Sass through the `sass` npm package; do not reintroduce `node-sass`.
- Use `frontend/package.json` and `frontend/package-lock.json` for frontend build dependencies.
- Third-party Django app static assets such as CKEditor, autocomplete-light, mptt, silk, and comment assets come from installed Python packages.
- PWA/root static files such as icons, manifest, and service worker live in `pwa/`.
- Forum static work stays in the sibling `../forum_instance` project unless explicitly coupled.

## Dependency Workflow

Main app dependencies are managed with uv through `pyproject.toml` and `uv.lock`.

Frontend build dependencies for Django-owned custom static assets are managed separately in `frontend/package.json` and `frontend/package-lock.json`.

For dependency details, read:

- `docs/engineering/dependencies/README.md`
- `docs/engineering/package-upgrades/`

Do not reintroduce checked-in main-app `requirements.in`, `requirements.txt`, or `constraints.txt` files unless the dependency workflow intentionally changes again.

Do not reintroduce the retired `am-front` submodule or Docker service unless the static ownership model intentionally changes again.

Keep forum dependency work isolated in the sibling project at `../forum_instance` unless the task explicitly asks for a coupled main/forum change.

## Documentation Layout

Use `docs/engineering/` for technical plans, investigations, architecture notes, upgrade reports, and implementation records.

Use `docs/business/` for future product, domain, operations, content, and non-code business documentation.

This repository now treats `docs/` as the durable knowledge base for people and agents. Before meaningful implementation work, read:

- `docs/README.md` for the knowledge-base workflow.
- `docs/business/README.md` and relevant notes under `docs/business/domains/` for domain context.
- `docs/engineering/decisions/` for accepted or proposed decisions that affect the change.
- `docs/work/` for the planning and result artifact workflow.

Planning is required before implementation when a change affects product behavior, domain rules, architecture, dependencies, data, security, or a workflow spanning multiple apps/services. Use `docs/work/plans/template.md` and create a dated plan under `docs/work/plans/` unless an equivalent plan already exists.

Small mechanical fixes do not need a full plan. Examples: typo fixes, formatting-only docs edits, small test expectation corrections, or comments that do not change behavior.

Write result artifacts under `docs/work/results/` when the work needs a durable execution summary, verification record, audit output, or follow-up list.

Update the durable knowledge base in the same change when implementation reveals new business rules, domain language, workflows, lifecycle states, constraints, or decisions.

When adding new investigation output, prefer a dated document under a topic folder, for example:

- `docs/work/plans/YYYY-MM-DD-topic.md`
- `docs/work/results/YYYY-MM-DD-topic.md`
- `docs/engineering/decisions/YYYY-MM-DD-topic.md`
- `docs/engineering/package-upgrades/YYYY-MM-DD-topic.md`
- `docs/engineering/security/YYYY-MM-DD-topic.md`
- `docs/business/domains/YYYY-MM-DD-topic.md`

## Working Rules


- Prefer Docker Compose for local verification because the app expects services from the parent `am-dev` environment.
- Avoid assuming host Python has project dependencies installed.
- Before package upgrades, check both main and forum requirements.
- Keep forum changes isolated unless the task explicitly asks for a coupled main/forum change.
- Do not remove user changes or generated local environment files.
