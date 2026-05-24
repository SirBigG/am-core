# Testing

Baseline verified on 2026-05-12 using the parent Docker Compose stack in `/Users/andriihots/Projects/am-dev`.

## Commands

Run from the parent `am-dev` folder:

```bash
docker compose exec core make test
docker compose exec forum_instance python manage.py test
```

`make test` inside the `core` container runs:

1. `make test_core`
2. `make test_api`
3. `make flake`

Do not run `test_core` and `test_api` in parallel unless the test database names are separated. Both use the same PostgreSQL test database name and will collide during database creation.

## Current Baseline

As of 2026-05-12 after Batch 6 dependency constraints:

- Core Django tests: 232 passing.
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
- Security header coverage for current `SecurityMiddleware`, clickjacking headers, and report-only CSP on the service worker endpoint, representative public/template pages, authenticated profile/diary pages, and Django admin login/index.
- Forum smoke and markdown coverage for anonymous home/topic/category/detail reads, login through SSO start, logout redirect, forum profile update authentication, basic markdown rendering, raw HTML escaping, and unsafe URL protocol stripping.
