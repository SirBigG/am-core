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

- `pyproject.toml` allows `>=3.12,<3.13`
- Docker uses Python `3.12.13` for both `core` and `forum_instance`
- Django 6 requires Python `>=3.12`, so moving to Django 6 means intentionally dropping Python 3.11 support.

Security review on 2026-05-11 found direct dependency risks in the main requirements:

- `Django==5.0.3`, upgraded to `Django==5.2.14` on 2026-05-12.
- `djangorestframework==3.15.1`, upgraded to `djangorestframework==3.17.1` on 2026-05-12.
- `Pillow==10.2.0`, upgraded to `Pillow==12.2.0` on 2026-05-12.
- `requests==2.31.0`, upgraded to `requests==2.34.0` on 2026-05-12.
- `social-auth-app-django==5.4.0`, upgraded to `social-auth-app-django==5.7.0` on 2026-05-12.
- `python-jose==3.3.0`, upgraded to `python-jose==3.5.0` on 2026-05-12.
- `lxml==5.1.0`, upgraded to `lxml==6.1.0` on 2026-05-12.

Batch 1 note:

- The old `social-auth-app-django[openidconnect]` extra was removed because pip reports that `social-auth-app-django==5.7.0` does not declare it.
- After the Batch 1 install, `docker compose exec core python -m pip check` passed with no broken requirements.
- After the Batch 1 install, direct dependency audit passed with no known vulnerabilities.

Batch 2 note:

- `core` and `forum_instance` Docker images were moved to `python:3.12.13-slim`; `pyproject.toml` now declares `>=3.12,<3.13`.
- Main app ecosystem pins were updated: `psycopg[c]==3.3.4`, `django-storages==1.14.6`, `boto3==1.43.6`, `daphne==4.2.1`, `selenium==4.43.0`, `openpyxl==3.1.5`, `phonenumbers==9.0.30`, `phonenumberslite==9.0.30`, `MarkupSafe==3.0.3`, `python-dateutil==2.9.0.post0`, `xlrd==2.0.2`, and `requests==2.34.0`.
- The obsolete Python 3 backport `ipaddress==1.0.23` was removed from the main requirements.
- Forum shared infrastructure pins were updated: `psycopg[c]==3.3.4`, `django-storages==1.14.6`, and `boto3==1.43.6`.
- `docker compose build core forum_instance`, `docker compose exec core python -m pip check`, `docker compose exec forum_instance python -m pip check`, and the main/forum test suites passed on Python 3.12.13.
- Direct main dependency audit passed with no known vulnerabilities after Batch 2.

Batch 4 note:

- Main helper/dev pins were updated on 2026-05-12: `django-autocomplete-light==4.0.0`, `django-ckeditor==6.7.3`, `django-mptt==0.18.0`, `django-phonenumber-field==8.4.0`, `django-rosetta==0.10.3`, `social-auth-app-django==5.9.0`, `django-taggit==6.1.0`, `django-recaptcha==4.1.0`, `django-comments-dab==3.0.0`, `django-silk==5.5.0`, `django_http2_push==0.0b2`, `factory-boy==3.3.3`, `flake8==7.3.0`, and `coverage==7.14.0`.
- Forum `social-auth-app-django` was also moved to `5.9.0`.
- `docker compose build core forum_instance`, `docker compose exec core make test`, `docker compose exec forum_instance python manage.py test`, both `pip check` commands, and the main direct dependency audit passed after Batch 4.

Batch 5 note:

- Main Docker geckodriver provisioning moved from `0.30.0` to `0.36.0` on 2026-05-12.
- The Dockerfile now chooses the Linux geckodriver archive for `amd64` or `arm64`, which matches the local Docker Compose setup.
- `core.companies.parser` now uses the system `geckodriver` or `GECKODRIVER_PATH` instead of downloading a driver at runtime with `webdriver_manager`.
- `webdriver_manager` was removed from `requirements.txt`.
- `docker compose build core`, `docker compose up -d core`, `docker compose exec core make test`, `docker compose exec core python -m pip check`, and the main direct dependency audit passed after Batch 5.

Forum-specific risk:

- `django-spirit==0.14.3` pins vulnerable `mistune==0.8.4`.
- `django-spirit==0.14.3` requires `Django<6,>=4.2`, so the forum blocks a simple whole-repo Django 6 upgrade.
- Forum audit still reports `mistune==0.8.4` vulnerabilities: `CVE-2026-44708`, `CVE-2026-44896`, and `CVE-2026-44897`; `CVE-2026-44897` lists `3.2.1` as a fixed version, but Spirit pins Mistune below that line.
- PyPI currently lists `django-spirit==0.14.3` as the latest Spirit release. Installed metadata pins `mistune==0.8.4` exactly, and Spirit subclasses Mistune 0.x parser/renderer internals, so upgrading to Mistune 3 requires a fork/vendor migration or forum replacement.

## Upgrade Strategy

Do not jump straight to latest packages without expanding tests around risky areas.

Current verified baseline as of 2026-05-12:

- After Batch 5 browser-driver cleanup, `docker compose exec core make test`: 232 core tests, 31 API tests, and flake8 passing.
- After Batch 4 package upgrades, `docker compose exec forum_instance python manage.py test`: 23 forum tests passing.
- Batch 3 started forum markdown characterization with regression coverage for basic markdown, HTTPS links, raw HTML escaping, and `javascript:` URL stripping.

Current upgrade-prep progress:

- Step 1 baseline is done.
- Step 2 auth/OIDC/forum SSO regression coverage is done.
- Step 3 public page and template smoke coverage is done for the planned high-traffic slices.
- Step 4 API contract coverage is partly done and now covers pagination envelopes, serializer field shape, auth-required endpoints, validation errors, event filtering, user-owned post listing, service reviews, user profile output, post view tracking, and useful-vote idempotency.
- Step 5 file/image/storage coverage is partly done and now covers post-photo WebP conversion, thumbnail file creation, uploaded file deletion, static asset versioning, CKEditor settings/widgets/rich-text fields, main S3 storage settings, and forum S3 storage settings.
- Step 6 security header coverage has started and now covers current `SecurityMiddleware`, clickjacking headers, a report-only CSP header, representative public page groups, authenticated profile/diary pages, and Django admin login/index. Violation cleanup and a path toward nonce/enforcement still remain.
- Step 7 forum coverage has started and now covers anonymous home/topic/category/detail reads, SSO login start, logout redirect, forum profile update auth behavior, storage settings, and markdown security behavior. A deliberate `django-spirit`/Mistune mitigation decision still remains.

Recommended order:

1. Make current tests reliably runnable through Docker Compose.
2. Add regression tests for auth, OIDC, forum SSO, public page smoke coverage, API contracts, file/image/storage behavior, and security headers.
3. Upgrade the main app first within the Django 5 line, preferably Django 5.2 LTS. Done for Batch 1 on 2026-05-12.
4. Add CSP in report-only mode before enforcing it.
5. Decide the forum path separately: keep/fork/patch/replace `django-spirit`.
6. Move to Django 6 only after forum compatibility is solved or isolated. Python 3.11 support has already been dropped in project metadata as of Batch 2.

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
