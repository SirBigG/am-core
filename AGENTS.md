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

Use `docs/engineering/` for durable investigations, architecture notes, upgrade reports, implementation records, and decisions.

Use `docs/business/` for future product, domain, operations, content, and non-code business documentation.

This repository now treats `docs/` as the durable knowledge base for people and agents. Before meaningful implementation work, read:

- `docs/README.md` for the knowledge-base workflow.
- `docs/business/README.md` and relevant notes under `docs/business/domains/` for domain context.
- `docs/engineering/decisions/` for accepted or proposed decisions that affect the change.
- `var/agents-work/plans/README.md` for the local planning workflow when that gitignored workspace exists.

Planning is required before implementation when a change affects product behavior, domain rules, architecture, dependencies, data, security, or a workflow spanning multiple apps/services. Create a dated local plan under `var/agents-work/plans/` unless an equivalent plan already exists. Local plans are gitignored, non-authoritative, and must not be committed.

Small mechanical fixes do not need a full plan. Examples: typo fixes, formatting-only docs edits, small test expectation corrections, or comments that do not change behavior.

Put task requirements in the owning task tracker and implementation or verification summaries in the pull request. Promote lasting knowledge into the relevant durable business or engineering docs. Existing files under `docs/work/` are historical records, not the destination for new plans.

### Content Operations Workspace

Editorial research, article refreshes, bulk content generation, API publication campaigns, and other content-only operations are an exception to the tracked `docs/work/` workflow.

- Store content plans, research notes, evidence packets, before/after snapshots, API audit logs, rollback data, review bundles, and execution summaries under the gitignored `content_refresh_runs/` directory.
- Store one-off content scripts under the corresponding run directory instead of the repository root. Keep them locally after the run when they may help reproduce, audit, or analyze the work.
- Do not add content-only plans or result artifacts to tracked documentation.
- Reusable application code, management commands, tests, migrations, and template/API changes still belong in the tracked codebase and follow the local planning rules when applicable.
- Before content work, read the local `content_refresh_runs/README.md` when it exists. That file is intentionally local and may contain the current operational directory convention without secrets.
- Never store API tokens, passwords, cookies, or other credentials in `content_refresh_runs/`; load them from the approved environment file at runtime.

Update the durable knowledge base in the same change when implementation reveals new business rules, domain language, workflows, lifecycle states, constraints, or decisions.

When adding durable investigation output, prefer a dated document under a topic folder, for example:

- `docs/engineering/decisions/YYYY-MM-DD-topic.md`
- `docs/engineering/package-upgrades/YYYY-MM-DD-topic.md`
- `docs/engineering/security/YYYY-MM-DD-topic.md`
- `docs/business/domains/YYYY-MM-DD-topic.md`

Delete local plans and supporting analysis when work completes or is abandoned,
after promoting any lasting knowledge into durable docs or decisions.

## Working Rules


- Prefer Docker Compose for local verification because the app expects services from the parent `am-dev` environment.
- Avoid assuming host Python has project dependencies installed.
- Before package upgrades, check both main and forum requirements.
- Keep forum changes isolated unless the task explicitly asks for a coupled main/forum change.
- Do not remove user changes or generated local environment files.
