# Upgrade History Through Python 3.14 And Django 6

- Date: 2026-05-24
- Status: Historical record

## Purpose

This note preserves dependency and upgrade findings that previously lived in `AGENTS.md`. Agent instructions should stay short; long-lived findings belong in engineering docs.

## Current Dependency Baseline

Runtime dependencies are managed by uv:

- `pyproject.toml` is the human-edited top-level dependency input.
- `uv.lock` is the locked transitive dependency set.
- The old main-app `requirements.in`, `requirements.txt`, and `constraints.txt` files were removed in Batch 11.

Install dependencies from the lock:

```bash
uv sync --frozen --all-groups
```

Current Python constraints:

- `pyproject.toml` allows `>=3.14,<3.15`.
- Docker uses Python `3.14.5` for `core`.
- `am-core` intentionally tracks the latest stable Python 3.14 line.

## Security Review Starting Point

The 2026-05-11 security review found direct dependency risks in the main requirements:

- `Django==5.0.3`, upgraded to `Django==5.2.14` on 2026-05-12.
- `djangorestframework==3.15.1`, upgraded to `djangorestframework==3.17.1` on 2026-05-12.
- `Pillow==10.2.0`, upgraded to `Pillow==12.2.0` on 2026-05-12.
- `requests==2.31.0`, upgraded to `requests==2.34.0` on 2026-05-12.
- `social-auth-app-django==5.4.0`, upgraded to `social-auth-app-django==5.7.0` on 2026-05-12.
- `python-jose==3.3.0`, upgraded to `python-jose==3.5.0` on 2026-05-12.
- `lxml==5.1.0`, upgraded to `lxml==6.1.0` on 2026-05-12.

## Batch Summary

- Batch 1: removed the obsolete `social-auth-app-django[openidconnect]` extra; `pip check` and direct dependency audit passed.
- Batch 2: moved `core` and `forum_instance` to Python `3.12.13-slim`; updated main ecosystem pins; removed obsolete `ipaddress`; main/forum checks and tests passed.
- Batch 4: updated helper/dev packages and forum `social-auth-app-django`; build, tests, `pip check`, and direct audit passed.
- Batch 5: moved geckodriver provisioning to `0.36.0`; stopped runtime driver downloads with `webdriver_manager`; core checks and tests passed.
- Batch 6: added requirements/constraints inputs for both services before the later uv migration; builds, checks, tests, and audit passed.
- Batch 7: moved the forum project out of `am-core` into `/Users/andriihots/Projects/am-dev/forum_instance`; forum and core verification passed.
- Batch 8: removed obsolete beta `django_http2_push`; added local `static_push`; core verification and audit passed.
- Batch 9: moved CSP report-only settings toward Django 6 naming and added `/csp/report/`; `make test` passed.
- Batch 10: upgraded main `am-core` to Django `6.0.5`; switched to Django built-in CSP middleware; fixed Django 6 `Product.save`; verification and audit passed.
- Batch 11: moved main dependency management to uv; removed old main requirements/constraints files; build, checks, tests, and lock-export audit passed.
- Batch 12: moved main Docker runtime to Python `3.14.5`; refreshed `uv.lock`; build, checks, tests, lock check, sync check, and lock-export audit passed.
- Batch 13: removed stale Poetry pre-commit hook; added `make check-deps`; dependency checks and pre-commit config validation passed.

## Forum-Specific Risk

The forum project now lives outside this repo at `/Users/andriihots/Projects/am-dev/forum_instance`.

Do not change forum dependencies as part of `am-core` package work unless explicitly requested.

Known forum risk:

- `django-spirit==0.14.3` pins vulnerable `mistune==0.8.4`.
- `django-spirit==0.14.3` requires `Django<6,>=4.2`.
- Reported Mistune vulnerabilities include `CVE-2026-44708`, `CVE-2026-44896`, and `CVE-2026-44897`.
- Spirit subclasses Mistune 0.x parser/renderer internals, so upgrading to Mistune 3 requires a fork/vendor migration or forum replacement.

## Upgrade Strategy Record

Do not jump straight to latest packages without expanding tests around risky areas.

Current verified baseline as of 2026-05-24:

- After Batch 12 Python 3.14.5 upgrade, `docker compose exec core make test`: 234 core tests, 31 API tests, and flake8 passing.
- After Batch 6 dependency constraints, `docker compose exec forum_instance python manage.py test`: 23 forum tests passing.
- Batch 3 started forum markdown characterization with regression coverage for basic markdown, HTTPS links, raw HTML escaping, and `javascript:` URL stripping.

Upgrade-prep progress:

- Step 1 baseline is done.
- Step 2 auth/OIDC/forum SSO regression coverage is done.
- Step 3 public page and template smoke coverage is done for the planned high-traffic slices.
- Step 4 API contract coverage is partly done and covers pagination envelopes, serializer field shape, auth-required endpoints, validation errors, event filtering, user-owned post listing, service reviews, user profile output, post view tracking, and useful-vote idempotency.
- Step 5 file/image/storage coverage is partly done and covers post-photo WebP conversion, thumbnail file creation, uploaded file deletion, static asset versioning, CKEditor settings/widgets/rich-text fields, main S3 storage settings, and forum S3 storage settings.
- Step 6 security header coverage has started and covers current `SecurityMiddleware`, clickjacking headers, Django 6 report-only CSP middleware, representative public page groups, authenticated profile/diary pages, and Django admin login/index.
- Step 7 forum coverage happened before the forum was moved out of `am-core`; future forum work belongs in the sibling `am-dev/forum_instance` project.

Detailed plan:

- `docs/engineering/package-upgrades/2026-05-11-package-upgrade-test-plan.md`
- `docs/engineering/testing/README.md`
