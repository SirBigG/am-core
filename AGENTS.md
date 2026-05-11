# AGENTS.md

Guidance for Codex and other coding agents working in this repository.

## Project Context

This repo is the `am-core` Django backend for AgroMega. It is usually run locally from the parent `am-dev` folder, not from this folder alone.

Local Docker Compose config:

- Compose file: `/Users/andriihots/Projects/am-dev/docker-compose.yml`
- Main service: `core`
- Forum service: `forum_instance`
- Database service: `db`
- Nginx service exposes local port `8000`
- The compose file mounts this repo as `./am-core:/am-core`
- The forum project lives in `forum_instance` and is mounted as `./am-core/forum_instance:/app`

Useful local commands from the parent folder:

```bash
docker compose ps
docker compose up
docker compose exec core ./manage.py test --settings=settings.test_settings
docker compose exec core ./manage.py test api --settings=settings.test_settings
docker compose exec core flake8
docker compose exec core make test
docker compose exec core make test_api
docker compose exec forum_instance python manage.py test
```

## Dependency Management Findings

Runtime dependencies are currently managed by:

- `requirements.txt`
- `forum_instance/requirements.txt`

`pyproject.toml` does not currently contain runtime dependencies; it mostly contains project metadata and tool configuration. There is no lock file or compiled constraints file yet.

Python constraints:

- `pyproject.toml` allows `>=3.11,<3.13`
- Docker uses Python `3.12.2`
- Django 6 requires Python `>=3.12`, so moving to Django 6 means intentionally dropping Python 3.11 support.

Security review on 2026-05-11 found direct dependency risks in the main requirements:

- `Django==5.0.3`
- `djangorestframework==3.15.1`
- `Pillow==10.2.0`
- `requests==2.31.0`
- `social-auth-app-django==5.4.0`
- `python-jose==3.3.0`
- `lxml==5.1.0`

Forum-specific risk:

- `django-spirit==0.14.3` pins vulnerable `mistune==0.8.4`.
- `django-spirit==0.14.3` requires `Django<6,>=4.2`, so the forum blocks a simple whole-repo Django 6 upgrade.

## Upgrade Strategy

Do not jump straight to latest packages without expanding tests around risky areas.

Current verified baseline as of 2026-05-12:

- `docker compose exec core make test`: 216 core tests, 31 API tests, and flake8 passing.
- `docker compose exec forum_instance python manage.py test`: 11 forum tests passing.

Current upgrade-prep progress:

- Step 1 baseline is done.
- Step 2 auth/OIDC/forum SSO regression coverage is done.
- Step 3 public page and template smoke coverage is done for the planned high-traffic slices.
- Step 4 API contract coverage is partly done and now covers pagination envelopes, serializer field shape, auth-required endpoints, validation errors, event filtering, user-owned post listing, service reviews, user profile output, post view tracking, and useful-vote idempotency.
- Step 5 file/image/storage coverage is partly done and now covers post-photo WebP conversion, thumbnail file creation, uploaded file deletion, static asset versioning, CKEditor settings/widgets/rich-text fields, main S3 storage settings, and forum S3 storage settings.
- Step 6 security header coverage has started and now covers current `SecurityMiddleware` and clickjacking headers. CSP report-only work still remains.

Recommended order:

1. Make current tests reliably runnable through Docker Compose.
2. Add regression tests for auth, OIDC, forum SSO, public page smoke coverage, API contracts, file/image/storage behavior, and security headers.
3. Upgrade the main app first within the Django 5 line, preferably Django 5.2 LTS.
4. Add CSP in report-only mode before enforcing it.
5. Decide the forum path separately: keep/fork/patch/replace `django-spirit`.
6. Move to Django 6 only after Python 3.11 support is dropped and forum compatibility is solved or isolated.

Detailed plan:

- `docs/engineering/package-upgrades/2026-05-11-package-upgrade-test-plan.md`
- `docs/engineering/testing/README.md`

## Documentation Layout

Use `docs/engineering/` for technical plans, investigations, architecture notes, upgrade reports, and implementation records.

Use `docs/business/` for future product, domain, operations, content, and non-code business documentation.

When adding new investigation output, prefer a dated document under a topic folder, for example:

- `docs/engineering/package-upgrades/YYYY-MM-DD-topic.md`
- `docs/engineering/security/YYYY-MM-DD-topic.md`
- `docs/business/YYYY-MM-DD-topic.md`

## Working Rules

- Prefer Docker Compose for local verification because the app expects services from the parent `am-dev` environment.
- Avoid assuming host Python has project dependencies installed.
- Before package upgrades, check both main and forum requirements.
- Keep forum changes isolated unless the task explicitly asks for a coupled main/forum change.
- Do not remove user changes or generated local environment files.
