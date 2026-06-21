# Testing

Baseline verified on 2026-05-12 using the parent Docker Compose stack in `/Users/andriihots/Projects/am-dev`.

## Commands

Run from the `am-core` folder:

```bash
just test
just forum-test
```

Use `just check-deps` after dependency or runtime metadata changes. It verifies that `uv.lock` is current and that the frozen uv sync would not change the installed environment.

`just test` runs:

1. `just test-core`
2. `just test-api`
3. `just flake`

Do not run `test_core` and `test_api` in parallel unless the test database names are separated. Both use the same PostgreSQL test database name and will collide during database creation.

## Current Baseline

As of 2026-05-24 after Batch 12 Python 3.14.5 upgrade:

- Core Django tests: 234 passing.
- API tests: 31 passing.
- Flake8: passing.
- Forum tests: 23 passing.

Batch 1 upgraded the main app to Django 5.2.14, DRF 3.17.1, Pillow 12.2.0, social-auth-app-django 5.7.0, python-jose 3.5.0, and lxml 6.1.0.

Batch 2 upgraded both Docker app runtimes to Python 3.12.13 and updated the ecosystem pins for storage, database, ASGI, browser tooling, spreadsheet/date/phone utilities, MarkupSafe, and requests 2.34.0. `docker compose exec core python -m pip check` and `docker compose exec forum_instance python -m pip check` passed with no broken requirements. The main direct dependency audit reported no known vulnerabilities; the forum audit still reports the known `django-spirit` transitive `mistune==0.8.4` vulnerabilities.

Batch 3 started forum markdown characterization. The expected forum count is now 23 after adding regression coverage for basic markdown rendering, safe HTTPS links, raw HTML escaping, and `javascript:` URL stripping from links and images.

Batch 4 updated Django helper libraries and dev/test pins: django-autocomplete-light, django-ckeditor, django-mptt, django-phonenumber-field, django-rosetta, social-auth-app-django, django-taggit, django-recaptcha, django-comments-dab, django-silk, django_http2_push, factory-boy, flake8, and coverage. Both services passed `pip check`; the main direct dependency audit still reports no known vulnerabilities, while the forum audit still reports only the known `django-spirit` transitive `mistune==0.8.4` vulnerabilities.

Batch 5 updated main Docker geckodriver provisioning from 0.30.0 to 0.36.0, added architecture-aware `amd64`/`arm64` driver downloads, removed runtime `webdriver_manager` usage from the parser path, and removed `webdriver_manager` from `requirements.txt`. The core image rebuild, `pip check`, main direct dependency audit, focused company parser tests, and full `make test` passed.

Batch 6 added transitive constraints for both services and wired Docker installs plus the main `Makefile` install path to use them. Both image rebuilds passed, both `pip check` commands passed, core `make test` passed, forum tests passed, and the main direct dependency audit still reports no known vulnerabilities.

Batch 8 removed the main app's obsolete beta `django_http2_push` dependency. Existing `{% static_push %}` template calls are now handled by a local compatibility tag that returns Django static asset URLs. The core image rebuild, absence check for `django-http2-push`, `pip check`, direct dependency audit, focused template-tag test, and full core `make test` passed.

Batch 9 moved CSP report-only configuration toward Django 6 setting names and added a `/csp/report/` endpoint for browser violation reports. Core `make test` passed with 236 core tests, 31 API tests, and flake8.

Batch 10 upgraded the main app to Django 6.0.5, switched report-only CSP to Django's built-in `ContentSecurityPolicyMiddleware`, removed the temporary custom CSP middleware, and fixed the Django 6 keyword-only `Model.save()` call in `core.companies.models.Product`. CKEditor stayed on `django-ckeditor==6.7.3`. The core image rebuild, `pip check`, Django system check, focused CSP tests, full core `make test`, and main direct dependency audit passed.

Batch 11 migrated the main app dependency workflow to uv. Direct dependencies now live in `pyproject.toml`, transitive dependencies are locked in `uv.lock`, and Docker installs the locked environment with `uv sync --frozen --all-groups --no-install-project --inexact`. The core image rebuild, container uv/Django version checks, `pip check`, Django system check, full core `make test`, and lock-export audit passed.

Batch 12 upgraded the main Docker runtime to Python 3.14.5 and tightened `pyproject.toml` to `>=3.14,<3.15`. Black and pre-commit Python targets were aligned to Python 3.14, and `uv.lock` was refreshed for the new runtime. The core image rebuild, runtime version checks, `pip check`, Django system check, uv lock/sync checks, full core `make test`, and lock-export audit passed.

Batch 13 cleaned up local tooling after the uv migration. The stale Poetry pre-commit hook and stale in-repo `release-forum` Makefile target were removed, and `make check-deps` now wraps the uv lock/sync checks. Dependency checks and pre-commit config validation passed.

Known warnings that remain useful upgrade signals:

- `django-ckeditor` warns that bundled CKEditor 4 has unfixed security issues.
- `pro_auth.User.email` is the `USERNAME_FIELD` but is not unique.
- Several tests emit timezone warnings for naive datetimes.
- Some list views emit unordered pagination warnings.

## Notes

`settings/test_settings.py` must define static and media URL settings so template tests can render through `django.contrib.staticfiles`.

The forum `manage.py` file is not executable in the container mount, so use `python manage.py test`.

## Current Coverage Additions

Completed upgrade-prep slices:

- Baseline command and settings cleanup for Docker Compose testing.
- Auth, OIDC, and forum SSO regression coverage.
- Public page and template smoke coverage for posts, events, registry, news, companies, and related high-traffic paths.
- API contract coverage for pagination envelopes, serializer field shape, authentication-required endpoints, create validation errors, event filtering, service reviews, user profile output, post view tracking, and useful-vote idempotency.
- File, image, and storage coverage for uploaded post photo WebP conversion, thumbnail file creation, uploaded file deletion, static asset versioning, CKEditor settings/widgets/rich-text fields, main S3 storage settings, and forum S3 storage settings.
- Security header coverage for current `SecurityMiddleware`, clickjacking headers, and Django 6 report-only CSP on the service worker endpoint, representative public/template pages, authenticated profile/diary pages, and Django admin login/index.
- Forum smoke and markdown coverage for anonymous home/topic/category/detail reads, login through SSO start, logout redirect, forum profile update authentication, basic markdown rendering, raw HTML escaping, and unsafe URL protocol stripping.
