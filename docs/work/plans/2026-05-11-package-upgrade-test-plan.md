# Package Upgrade Test Plan

Created: 2026-05-11

## Current Dependency Shape

The main service now uses uv for dependency management. `pyproject.toml` contains the direct dependencies and `uv.lock` pins the transitive dependency set.

The main Docker image uses Python 3.14.5. The main app moved to Django 6.0.5 in Batch 10.

Batch 11 replaced the old main-app `requirements.in`, `requirements.txt`, and `constraints.txt` workflow with uv.
Batch 12 moved the main Docker runtime and project metadata to Python 3.14.

## Security Findings

`pip-audit` was run on direct pinned main dependencies with `--no-deps` because the host Python 3.14 cannot build the currently pinned `Pillow==10.2.0`. It found vulnerabilities in:

- `Django==5.0.3`; minimum fixed line is at least `5.0.14`, but Django 5.0 is no longer the best target.
- `djangorestframework==3.15.1`; fix `3.15.2`.
- `Pillow==10.2.0`; full current fix target `12.2.0`.
- `requests==2.31.0`; fix at least `2.33.0`.
- `social-auth-app-django==5.4.0`; fix at least `5.6.0`.
- `python-jose==3.3.0`; fix `3.4.0`.
- `lxml==5.1.0`; fix `6.1.0`.

The forum full dependency audit found `mistune==0.8.4`, pulled by `django-spirit==0.14.3`, with CVEs fixed in `mistune==3.2.1`. The forum was moved out of `am-core` into the sibling `../forum_instance` project, and forum dependency changes are intentionally out of scope for this `am-core` upgrade thread unless requested separately.

## Upgrade Feasibility

Recommended sequence:

1. Patch within the Django 5 line first: move main app to Django 5.2 LTS if compatible, and apply security updates for DRF, Pillow, requests, social auth, python-jose, and lxml.
2. Keep forum dependency decisions outside `am-core`; the forum now lives in the sibling `../forum_instance` project.
3. Add CSP in report-only mode before enforcing it. Done through Django 6's built-in `ContentSecurityPolicyMiddleware` and `SECURE_CSP_REPORT_ONLY` in Batch 10.
4. Move the main app to Django 6 after main-app CSP and CKEditor risks are understood. Done for `am-core` in Batch 10. Python 3.11 support was intentionally dropped in Batch 2.

Known compatibility pressure:

- `Django==6.0.5` supports Python 3.12, 3.13, and 3.14; `am-core` now runs on Python 3.14.5.
- The sibling forum project still uses `django-spirit==0.14.3`, which requires `Django<6,>=4.2` and pins vulnerable `mistune==0.8.4`; treat that as outside this repo's upgrade scope.
- `social-auth-app-django==5.9.0` requires `Django>=5.2`.
- `django-autocomplete-light==4.0.0` requires `Django>=5.2`.

## Batch 1 Implementation Result

Completed on 2026-05-12 for the main app requirements.

Updated direct pins:

- `Django==5.0.3` to `Django==5.2.14`.
- `djangorestframework==3.15.1` to `djangorestframework==3.17.1`.
- `Pillow==10.2.0` to `Pillow==12.2.0`.
- `requests==2.31.0` to `requests==2.34.0`.
- `social-auth-app-django[openidconnect]==5.4.0` to `social-auth-app-django==5.7.0`.
- `python-jose==3.3.0` to `python-jose==3.5.0`.
- `lxml==5.1.0` to `lxml==6.1.0`.

The stale `openidconnect` extra was removed from `social-auth-app-django` because pip reports that version `5.7.0` no longer declares that extra. The installed package still pulls the current `social-auth-core` dependency used by the project OIDC tests.

Verification commands run from the parent `am-dev` folder:

- `docker compose exec core python -m pip install -r requirements.txt`: passed.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.
- `docker compose exec core python manage.py check --settings=settings.test_settings`: passed with existing warnings only.
- `docker compose exec core make test`: passed, 231 core tests, 31 API tests, and flake8.
- `docker compose exec forum_instance python manage.py test`: passed, 19 forum tests.

Residual risks after Batch 1:

- `django-ckeditor` still warns that bundled CKEditor 4 has unfixed security issues.
- `pro_auth.User.email` remains the authentication field but is not unique.
- Some test fixtures still emit naive datetime warnings.
- Some list views still emit unordered pagination warnings.
- The forum still carries the separate `django-spirit` and vulnerable `mistune==0.8.4` decision.
- There is still no lock file or compiled constraints file, so reproducible resolution remains a follow-up before broader package cleanup.

## Batch 2 Implementation Result

Completed on 2026-05-12 for the main and forum Docker runtimes.

Runtime changes:

- `Dockerfile` moved from `python:3.12.2-slim` to `python:3.12.13-slim`.
- `forum_instance/Dockerfile` moved from floating `python:3.11-slim` to pinned `python:3.12.13-slim`.
- `pyproject.toml` moved from `python = ">=3.11,<3.13"` to `python = ">=3.12,<3.13"`.
- Black target version moved to `py312`.

Main app direct pin updates:

- `MarkupSafe==2.1.5` to `MarkupSafe==3.0.3`.
- `phonenumbers==8.13.32` to `phonenumbers==9.0.30`.
- `phonenumberslite==8.13.32` to `phonenumberslite==9.0.30`.
- `psycopg[c]==3.1.18` to `psycopg[c]==3.3.4`.
- `python-dateutil==2.8.2` to `python-dateutil==2.9.0.post0`.
- `requests==2.33.1` to `requests==2.34.0`.
- `xlrd==2.0.1` to `xlrd==2.0.2`.
- `daphne==4.1.0` to `daphne==4.2.1`.
- `selenium==4.18.1` to `selenium==4.43.0`.
- `webdriver_manager==3.5.0` to `webdriver_manager==4.0.2`; later removed in Batch 5 after switching parser code to the system `geckodriver`.
- `openpyxl==3.1.2` to `openpyxl==3.1.5`.
- `boto3==1.35.6` to `boto3==1.43.6`.
- `django-storages==1.14.4` to `django-storages==1.14.6`.
- Removed obsolete `ipaddress==1.0.23`; Python 3 provides `ipaddress` in the standard library.

Forum direct pin updates:

- `psycopg[c]==3.1.18` to `psycopg[c]==3.3.4`.
- `django-storages==1.14.4` to `django-storages==1.14.6`.
- `boto3==1.35.6` to `boto3==1.43.6`.

Verification commands run from the parent `am-dev` folder:

- `docker compose build core forum_instance`: passed.
- `docker compose up -d core forum_instance`: passed.
- `docker compose exec core python --version`: `Python 3.12.13`.
- `docker compose exec forum_instance python --version`: `Python 3.12.13`.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec forum_instance python -m pip check`: passed with no broken requirements.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r forum_instance/requirements.txt --no-deps`: still reports the known `mistune==0.8.4` vulnerabilities from `django-spirit`.
- `docker compose exec core make test`: passed, 231 core tests, 31 API tests, and flake8.
- `docker compose exec forum_instance python manage.py test`: passed, 19 forum tests.

Residual risks after Batch 2:

- The forum `django-spirit`/Mistune path remains the largest security blocker.
- Browser-driver provisioning was revisited in Batch 5.
- There is still no lock file or compiled constraints file, so transitive dependency versions float between builds.

## Batch 3 Forum Markdown Characterization

Started on 2026-05-12 for the forum security blocker.

Findings:

- PyPI currently lists `django-spirit==0.14.3` as the latest Spirit release, with compatibility for Django 4.2 LTS and 5.2 LTS.
- Installed package metadata confirms `django-spirit==0.14.3` requires `mistune==0.8.4` exactly, not a loose range.
- Spirit's markdown layer subclasses Mistune 0.x internals: `mistune.Markdown`, `mistune.Renderer`, `mistune.BlockLexer`, `mistune.InlineLexer`, and grammar objects. Moving to `mistune==3.2.1` requires a renderer/parser migration or a maintained fork; it cannot be handled as a simple requirements override.

Implementation:

- Added forum markdown regression coverage for basic markdown rendering, allowed HTTPS links, raw HTML escaping, and stripping `javascript:` URLs from links and images.

Next practical options:

1. Fork or vendor the minimal Spirit markdown stack and migrate it to Mistune 3 while keeping the current forum models/views/templates.
2. Replace Spirit with a maintained forum package or custom lightweight forum surface.
3. Keep Spirit temporarily on Django 5.2 and accept the remaining forum audit finding with an explicit risk exception while prioritizing CSP and main-app updates.

## Batch 4 Helper And Dev Dependency Cleanup

Completed on 2026-05-12 for Django 5.2-compatible helper packages and dev/test tools.

Main app direct pin updates:

- `django-autocomplete-light==3.11.0` to `django-autocomplete-light==4.0.0`.
- `django-ckeditor==6.7.1` to `django-ckeditor==6.7.3`.
- `django-mptt==0.16.0` to `django-mptt==0.18.0`.
- `django-phonenumber-field==7.3.0` to `django-phonenumber-field==8.4.0`.
- `django-rosetta==0.10.0` to `django-rosetta==0.10.3`.
- `social-auth-app-django==5.7.0` to `social-auth-app-django==5.9.0`.
- `django-taggit==5.0.1` to `django-taggit==6.1.0`.
- `django-recaptcha==4.0.0` to `django-recaptcha==4.1.0`.
- `django-comments-dab==2.8.0` to `django-comments-dab==3.0.0`.
- `django-silk==5.1.0` to `django-silk==5.5.0`.
- Pinned previously floating dev/test tools: `factory-boy==3.3.3`, `flake8==7.3.0`, and `coverage==7.14.0`.
- Pinned previously floating runtime package `django_http2_push==0.0b2`.

Forum direct pin updates:

- `social-auth-app-django==5.7.0` to `social-auth-app-django==5.9.0`.

Verification commands run from the parent `am-dev` folder:

- `docker compose exec core python -m pip install -r requirements.txt`: passed.
- `docker compose exec forum_instance python -m pip install -r requirements.txt`: passed.
- `docker compose build core forum_instance`: passed.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec forum_instance python -m pip check`: passed with no broken requirements.
- `docker compose exec core python manage.py check --settings=settings.test_settings`: passed with existing CKEditor and non-unique-email warnings only.
- `docker compose exec forum_instance python manage.py check`: passed.
- `docker compose exec core make test`: passed, 231 core tests, 31 API tests, and flake8.
- `docker compose exec forum_instance python manage.py test`: passed, 23 forum tests.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r forum_instance/requirements.txt --no-deps`: still reports only the known `mistune==0.8.4` vulnerabilities from `django-spirit`.

Residual risks after Batch 4:

- The forum `django-spirit`/Mistune path remains unresolved.
- `django-ckeditor==6.7.3` still bundles CKEditor 4.22.1 and keeps the upstream warning about unfixed CKEditor 4 security issues.
- `django_http2_push==0.0b2` was still pinned at this point, but later removed in Batch 8.

## Batch 5 Browser Driver Cleanup

Completed on 2026-05-12 for the main parser/browser automation runtime.

Changes:

- `Dockerfile` moved geckodriver from `0.30.0` to `0.36.0`.
- Geckodriver download now chooses the Linux archive by image architecture: `amd64` uses `linux64`, and `arm64` uses `linux-aarch64`.
- `core.companies.parser` now creates Firefox with the system `geckodriver`, or the path configured by `GECKODRIVER_PATH`.
- Removed runtime downloads through `webdriver_manager`.
- Removed `webdriver_manager==4.0.2` from `requirements.txt`.
- Added a regression test for the configured geckodriver path used by the parser driver factory.

Verification commands run from the parent `am-dev` folder:

- `docker compose exec core ./manage.py test core.companies.tests --settings=settings.test_settings`: passed, 4 tests.
- `docker compose build core`: passed and downloaded the `geckodriver-v0.36.0-linux-aarch64.tar.gz` archive for the current local `arm64` image.
- `docker compose up -d core`: passed.
- `docker compose exec core geckodriver --version`: `geckodriver 0.36.0`.
- `docker compose exec core python -m pip show webdriver-manager`: package not found.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec core make test`: passed, 232 core tests, 31 API tests, and flake8.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.

Residual risks after Batch 5:

- The forum `django-spirit`/Mistune path remains unresolved.
- `django-ckeditor==6.7.3` still bundles CKEditor 4.22.1 and keeps the upstream warning about unfixed CKEditor 4 security issues.
- There is still no lock file or compiled constraints file, so transitive dependency versions float between builds.

## Batch 6 Dependency Constraints

Completed on 2026-05-12 for reproducible Python dependency installs.

Changes:

- Added `requirements.in` and `forum_instance/requirements.in` as human-edited top-level dependency inputs.
- Added `constraints.txt` and `forum_instance/constraints.txt` from the verified Docker Compose environments.
- Updated the main `Dockerfile` to copy `constraints.txt` and install with `pip install -r requirements.txt -c constraints.txt`.
- Updated `forum_instance/Dockerfile` to copy `constraints.txt` and install with `pip install --no-cache-dir -r requirements.txt -c constraints.txt`.
- Updated the main `Makefile` `update` target to install with constraints.
- Added `docs/engineering/dependencies/README.md` for the dependency file workflow.

Verification commands run from the parent `am-dev` folder:

- `docker compose exec core python -m pip install -r requirements.txt -c constraints.txt`: passed.
- `docker compose exec forum_instance python -m pip install -r requirements.txt -c constraints.txt`: passed.
- `docker compose build core forum_instance`: passed.
- `docker compose up -d core forum_instance`: passed.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec forum_instance python -m pip check`: passed with no broken requirements.
- `docker compose exec core make test`: passed, 232 core tests, 31 API tests, and flake8.
- `docker compose exec forum_instance python manage.py test`: passed, 23 forum tests.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r forum_instance/requirements.txt --no-deps`: still reports only the known `mistune==0.8.4` vulnerabilities from `django-spirit`.

Residual risks after Batch 6:

- The constraints files are not hash-locked. Use `pip-tools` with hashes later if stronger supply-chain reproducibility is needed.
- The forum `django-spirit`/Mistune path remains unresolved.
- `django-ckeditor==6.7.3` still bundles CKEditor 4.22.1 and keeps the upstream warning about unfixed CKEditor 4 security issues.

## Batch 7 Forum Relocation

Completed on 2026-05-24 to keep forum dependency decisions out of the `am-core` package upgrade thread.

Changes:

- Moved the forum project from `am-core/forum_instance` to the sibling path `../forum_instance`.
- Updated parent `docker-compose.yml` so `forum_instance` builds from `./forum_instance` and mounts `./forum_instance:/app`.
- Added parent `.gitignore` entries for generated forum artifacts: `forum_instance/staticfiles/`, `forum_instance/st_search/`, and compiled forum translation files.
- Updated `am-core` docs to treat the forum as an external sibling project.

Verification commands run from the parent `am-dev` folder:

- `docker compose config --services`: passed.
- `docker compose build forum_instance`: passed.
- `docker compose up -d forum_instance`: passed.
- `docker inspect am-forum-instance --format '{{json .Mounts}}'`: confirmed `../forum_instance` mounts to `/app`.
- `docker compose exec forum_instance python -m pip check`: passed with no broken requirements.
- `docker compose exec forum_instance python manage.py test`: passed, 23 tests.
- `docker compose exec core make test`: passed, 232 core tests, 31 API tests, and flake8.

Residual risks after Batch 7:

- Forum dependencies are intentionally unchanged and remain outside this `am-core` upgrade scope.
- The sibling forum still carries the known `django-spirit`/Mistune risk if it remains deployed.
- `am-core` still needs a CKEditor 4 decision and a main-app CSP/Django 6 path.

## Current Test Coverage Shape

The repo has about 25 test files:

- Main app: 19 test files, roughly 2,830 lines.
- API app: 5 test files, roughly 307 lines.
- Forum app: 23 local tests covering SSO redirects, the forum user sync pipeline, forum smoke reads, forum storage settings, and markdown security behavior. The installed Spirit package also carries its own markdown tests, but they are not part of this repo's default forum test suite.

Coverage is strongest around diary flows, public rendered page smoke tests, auth/OIDC/forum SSO, and some model/form/view behavior. Coverage is still thin or missing for analytics, storage settings, CSP/security headers, and dependency-heavy integrations like CKEditor, reCAPTCHA, and deeper OAuth Toolkit token endpoint behavior.

## Pre-Upgrade Test Plan

### Step 1: Make The Existing Suite Reliably Runnable

- Add a documented local test command that runs on Python 3.12.
- Decide whether tests use PostgreSQL or SQLite. Current test settings expect PostgreSQL environment variables and database `test_db`.
- Add a CI or local script that runs `manage.py test --settings=settings.test_settings`, `manage.py test api --settings=settings.test_settings`, and linting.
- Add `pip-audit` as an explicit check, ideally against compiled locked requirements.

Exit criteria:

- One command runs all current tests from a clean checkout.
- Direct dependency audit is repeatable.
- Dependency resolution is reproducible.

### Step 2: Authentication And OIDC Regression Tests

Add tests for the main app as OIDC provider:

- OIDC application creation command behavior. Done.
- Login/logout redirects and `LOGIN_REDIRECT_URL`.
- Token/userinfo/JWKS endpoint availability enough to protect forum SSO.
- Custom user model authentication by email.
- Social auth pipeline custom `create_user` and extra-data behavior. Done.

Add tests for forum SSO:

- `/sso/start/` redirects to the configured provider. Done.
- `/complete/oidc/` pipeline creates or updates forum users. Pipeline covered; callback endpoint still needs an integration test.
- Forum logout redirects back to main app logout. Done.
- Anonymous read access remains available, write/login actions still route through SSO.

Exit criteria:

- We can upgrade `django-oauth-toolkit` and `social-auth-app-django` with confidence.
- Forum auth behavior is protected before touching Spirit or Django versions.

### Step 3: Public Page And Template Smoke Tests

Add smoke tests for high-traffic template pages:

- Home page. Done.
- Posts list/detail/search/gallery paths. Done.
- Category pages. Done.
- Adverts list/detail/create/update paths. List/create/detail coverage exists; profile update coverage exists elsewhere.
- Events list/detail/create paths. Done.
- Services feedback/reviews paths. Existing coverage.
- Diary public list/detail and profile diary flows. Existing coverage.
- Registry pages. Done.
- News list/detail pages. Done.
- Company list/detail pages. Done.

For each page, assert status code, selected template, key context variables, and absence of template rendering errors.

Exit criteria:

- Django template/context changes and middleware changes are caught early.

### Step 4: API Contract Tests

Broaden API tests around:

- Pagination shape. Done for post list endpoints.
- Filtering and search parameters. Event active/future filtering covered; broader search parameter coverage still remains.
- Authentication-required endpoints. Done for user posts, event creation, user profile, and service review creation.
- Create/update/delete permissions. Create permissions covered for the main exposed create endpoints; update/delete coverage still remains where those actions are exposed.
- Serializer output fields for posts, events, services, classifiers, and auth endpoints. Done for key read and create responses.
- Error status and validation response shape. Done for event creation, user post creation, and service review creation.

Additional behavior covered:

- User post list only returns posts owned by the authenticated user.
- User post creation now validates required uploaded photos instead of raising a server error.
- Post view tracking preserves current per-request hit increment behavior.
- Post useful votes are idempotent for the same JSON payload.

Exit criteria:

- `djangorestframework` upgrades can be verified by response contracts, not just status codes.

### Step 5: File, Image, And Storage Tests

Add tests for:

- Image upload and thumbnail/image URL handling. Done for post photos: upload resize/WebP conversion, thumbnail file generation, and uploaded file deletion.
- CKEditor rich text fields and upload paths. Settings, public form widgets, rendered widget template contract, and rich-text model fields are covered. Real CKEditor upload endpoint coverage is not applicable yet because the project does not include `ckeditor_uploader` URLs.
- `core.utils.storage.VersionedStaticFilesStorage`. Done for media-version query strings and CKEditor asset exclusion.
- Local media handling under test settings. Done for isolated post-photo media files with temporary `MEDIA_ROOT`.
- S3 storage settings construction in `settings/live.py` and forum S3 settings without real AWS calls. Done for main app S3 backend locations, endpoint URL normalization, forum S3 endpoint normalization, bucket media URL, and custom-domain media URL.

Additional behavior covered:

- Main live settings now accept `AWS_S3_ENDPOINT_URL` with or without an existing URL scheme.
- CKEditor upgrade risk is now covered at the project integration boundary: configured paths, widget rendering, public form usage, and model field types.

Exit criteria:

- Pillow, django-storages, boto3, and CKEditor updates are covered.

### Step 6: Security Header And CSP Tests

Before enforcing CSP:

- Add tests that `SecurityMiddleware` headers are present. Done for `X-Content-Type-Options`, `Referrer-Policy`, and `Cross-Origin-Opener-Policy` on `/service-worker.js`.
- Add tests that clickjacking headers are present. Done for `X-Frame-Options`.
- Add report-only CSP tests for public pages. Done for representative pages: home, post detail, event list, CDN-heavy event form, login, reCAPTCHA feedback, and news list with external image data.
- Add report-only CSP tests for authenticated and admin pages. Done for profile dashboard, diary list, diary detail, diary item form, Django admin login, and Django admin index.
- Inventory inline scripts/styles and external assets currently used by templates. Initial inventory found inline scripts/styles and handlers across main templates, profile/diary pages, forum templates, plus external assets from Google Tag Manager, Google Ads, Google reCAPTCHA, jsDelivr, cdnjs, StackPath Bootstrap, code.jquery.com, Facebook, Telegram, and MathJax.
- Add tests for any CSP nonce/context processor behavior if using Django 6 or `django-csp`.
- Verify pages using Bootstrap CDN, CKEditor, reCAPTCHA, and admin assets receive a policy that does not break rendering. Done for Bootstrap/CDN-heavy event form, reCAPTCHA feedback page, CKEditor-heavy diary item form, profile/diary pages, and Django admin login/index.

Exit criteria:

- CSP can start in report-only mode without blocking core pages.
- Enforcement can be done page group by page group.

Current report-only policy:

- Implemented by Django's built-in `django.middleware.csp.ContentSecurityPolicyMiddleware`.
- Configured in `settings.settings.SECURE_CSP_REPORT_ONLY`.
- Intentionally allows current inline scripts/styles and known external assets so violations can be observed before any enforcement work.
- Reports violations to `/csp/report/` through the `report-uri` directive.

## Batch 8 Main HTTP/2 Push Removal

Completed on 2026-05-24 for the main app.

Changes:

- Removed the obsolete beta `django_http2_push==0.0b2` dependency from `requirements.in`, `requirements.txt`, and `constraints.txt`.
- Removed `django_http2_push` from `INSTALLED_APPS` and `PushHttp2Middleware` from `MIDDLEWARE`.
- Added a local `static_push` template tag that delegates to Django's built-in static asset URL helper so existing templates keep rendering.
- Added a regression test for `{% static_push %}` template rendering.

Verification:

- `docker compose build core`: passed.
- `docker compose up -d core`: passed.
- `docker compose exec core python -m pip show django-http2-push`: confirmed the package is not installed.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec core ./manage.py test core.utils.tests.test_static_push --settings=settings.test_settings`: passed.
- `docker compose exec core make test`: passed, 233 core tests, 31 API tests, and flake8.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.

## Batch 9 CSP Report Pipeline

Completed on 2026-05-24 for Django 6 CSP readiness.

Current package availability checked with `python3 -m pip index versions`:

- `Django==6.0.5` is the latest Django release.
- `django-ckeditor==6.7.3` is already the latest `django-ckeditor` release, so the CKEditor 4 warning cannot be solved by a simple pin bump.
- `django-ckeditor-5==0.2.20` is available, but adopting it is an editor migration and licensing/product decision rather than a narrow package update.

Changes:

- Added `SECURE_CSP_REPORT_ONLY` as the primary CSP report-only setting and kept `CONTENT_SECURITY_POLICY_REPORT_ONLY` as a Django 5 compatibility alias.
- Updated the custom report-only middleware to prefer `SECURE_CSP_REPORT_ONLY`.
- Added `/csp/report/` as a CSRF-exempt POST endpoint for browser CSP violation reports.
- Added `report-uri /csp/report/` to the report-only CSP.
- Added tests for the report endpoint, the `report-uri` directive, and the Django 6 setting-name preference.

Verification:

- `docker compose exec core ./manage.py test core.utils.tests.test_security_headers --settings=settings.test_settings`: passed.
- `docker compose exec core make test`: passed, 236 core tests, 31 API tests, and flake8.

## Batch 10 Main Django 6 Upgrade

Completed on 2026-05-24 for the main `am-core` service.

Changes:

- Updated the main app from `Django==5.2.14` to `Django==6.0.5` in `requirements.in`, `requirements.txt`, and `constraints.txt`.
- Switched `settings.settings.MIDDLEWARE` from the temporary `core.utils.security.ContentSecurityPolicyReportOnlyMiddleware` to Django's built-in `django.middleware.csp.ContentSecurityPolicyMiddleware`.
- Removed the temporary custom CSP middleware and the Django 5 compatibility alias `CONTENT_SECURITY_POLICY_REPORT_ONLY`.
- Kept `SECURE_CSP_REPORT_ONLY` as the active report-only CSP configuration.
- Left `django-ckeditor==6.7.3` unchanged by request; CKEditor 4 remains a separate security/product decision.
- Updated `core.companies.models.Product.save()` to call `super().save()` with keyword arguments, matching Django 6's keyword-only model save API.

Verification:

- `docker compose build core`: passed and installed `Django-6.0.5`.
- `docker compose up -d core`: passed.
- `docker compose exec core python -c "import django; print(django.get_version())"`: `6.0.5`.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec core ./manage.py check --settings=settings.test_settings`: passed with existing CKEditor and non-unique-email warnings only.
- `docker compose exec core ./manage.py test core.utils.tests.test_security_headers --settings=settings.test_settings`: passed, 5 tests.
- `docker compose exec core ./manage.py test core.companies.tests.CompanyPublicViewTests.test_company_detail_renders_products --settings=settings.test_settings`: passed.
- `docker compose exec core make test`: passed, 234 core tests, 31 API tests, and flake8.
- `env PYTHONPATH=/private/tmp/pip-audit-tool python3 -m pip_audit -r requirements.txt --no-deps`: passed with no known direct dependency vulnerabilities.

Residual risks after Batch 10:

- `django-ckeditor==6.7.3` still bundles CKEditor 4 and emits the upstream unsupported/security warning. This was intentionally not migrated to CKEditor 5 because that is a licensing/product decision.
- The sibling forum project remains outside `am-core`; if it is still deployed, its `django-spirit`/Mistune risk still needs a separate decision.
- CSP is still report-only. Enforcement still needs violation cleanup, nonce work where appropriate, and page-group rollout.

## Batch 11 Main uv Migration

Completed on 2026-05-24 for the main `am-core` service.

Changes:

- Moved direct main-app dependencies into PEP 621 `[project]` metadata in `pyproject.toml`.
- Added a uv `dev` dependency group for `coverage`, `factory-boy`, and `flake8`.
- Added `uv.lock` as the locked transitive dependency set.
- Removed the old main-app `requirements.in`, `requirements.txt`, and `constraints.txt` files.
- Updated `Dockerfile` to install dependencies with `uv sync --frozen --all-groups --no-install-project --inexact`.
- Set `UV_PROJECT_ENVIRONMENT=/usr/local` for Docker installs so local Docker Compose bind mounts do not hide dependencies under `/am-core/.venv`.
- Updated the main `Makefile` `update` target to use uv.
- Updated dependency docs and agent notes for the uv workflow.

Verification:

- `uv lock`: passed inside the Linux `core` container. The local Homebrew/macOS uv binary panicked under the Codex sandbox, so lock generation was done in Docker.
- `docker compose build core`: passed and installed dependencies from `uv.lock`.
- `docker compose up -d core`: passed.
- `docker compose exec core uv --version`: `uv 0.9.21`.
- `docker compose exec core python -c "import django; print(django.get_version())"`: `6.0.5`.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec core ./manage.py check --settings=settings.test_settings`: passed with existing CKEditor and non-unique-email warnings only.
- `docker compose exec core make test`: passed, 234 core tests, 31 API tests, and flake8.
- `docker compose exec core sh -c 'uv export --no-hashes --format requirements-txt --all-groups --output-file /tmp/am-core-uv-export.txt && uv tool run pip-audit -r /tmp/am-core-uv-export.txt'`: passed with no known vulnerabilities.

## Batch 12 Python 3.14 Runtime

Completed on 2026-05-24 for the main `am-core` service.

Changes:

- Updated the main Docker image from `python:3.12.13-slim` to `python:3.14.5-slim`.
- Updated `pyproject.toml` from `>=3.12,<3.13` to `>=3.14,<3.15`.
- Refreshed `uv.lock` for the Python 3.14 runtime.
- Aligned Black and pre-commit Python targets to Python 3.14.
- Removed Debian `python3-dev` from Docker build dependencies so the image does not install an extra distro Python toolchain beside the official Python runtime.

Verification:

- `docker compose build core`: passed and installed the locked uv environment on Python 3.14.5.
- `docker compose up -d core`: passed.
- `docker compose exec core python --version`: `Python 3.14.5`.
- `docker compose exec core python -c "import django; print(django.get_version())"`: `6.0.5`.
- `docker compose exec core python -m pip check`: passed with no broken requirements.
- `docker compose exec core ./manage.py check --settings=settings.test_settings`: passed with existing CKEditor and non-unique-email warnings only.
- `docker compose exec core uv lock --check`: passed.
- `docker compose exec core uv sync --frozen --all-groups --no-install-project --inexact --check`: passed with no changes.
- `docker compose exec core make test`: passed, 234 core tests, 31 API tests, and flake8.
- `docker compose exec core sh -c 'uv export --no-hashes --format requirements-txt --all-groups --output-file /tmp/am-core-uv-export.txt && uv tool run pip-audit -r /tmp/am-core-uv-export.txt'`: passed with no known vulnerabilities.

Residual risks after Batch 12:

- Python 3.14 narrows the supported runtime window for `am-core`; deploy targets must provide Python 3.14-compatible images.
- `django-ckeditor==6.7.3` still bundles CKEditor 4 and emits the upstream unsupported/security warning. This remains a separate product/licensing decision.
- CSP is still report-only. Enforcement still needs violation cleanup, nonce work where appropriate, and page-group rollout.

## Batch 13 Tooling Cleanup

Completed on 2026-05-24 for the main `am-core` service.

Changes:

- Removed the stale Poetry pre-commit hook after the main dependency workflow moved to uv.
- Added `make check-deps`, which runs `uv lock --check` and `uv sync --frozen --all-groups --no-install-project --inexact --check`.
- Removed the stale in-repo `release-forum` Makefile target because the forum project now lives outside `am-core`.
- Updated README and dependency/testing docs with the uv dependency check command.

Verification:

- `docker compose exec core make check-deps`: passed.
- `docker compose exec core uv tool run pre-commit validate-config`: passed.

### Step 7: Forum Dependency Decision

Before upgrading forum dependencies:

- Add minimal forum smoke tests: home, topic list, category topic list, topic detail, login start, logout, authenticated profile update, and profile update auth redirect. Done.
- Decide between three paths for `django-spirit`:
  - Keep Spirit temporarily and accept Django `<6` for the forum.
  - Fork/patch Spirit to remove the vulnerable Mistune pin and test parser behavior.
  - Replace Spirit with another maintained forum approach.

Exit criteria:

- The vulnerable Mistune dependency has a deliberate mitigation path.
- Forum and main-app Django versions are intentionally coupled or intentionally separated.

## Suggested Upgrade Batches

Batch 1, security patch without framework jump:

- Done on 2026-05-12 for the main app: Django 5.2.14, DRF 3.17.1, requests 2.34.0, python-jose 3.5.0, social-auth-app-django 5.7.0, Pillow 12.2.0, and lxml 6.1.0.

Batch 2, ecosystem cleanup:

- Done on 2026-05-12: boto3, django-storages, psycopg, daphne, selenium, openpyxl, phonenumbers, MarkupSafe, python-dateutil, xlrd, Python 3.12.13 Docker images, and removal of obsolete `ipaddress`.
- Done on 2026-05-12 in Batch 4: pin currently unpinned dev/test dependencies and update Django 5.2-compatible helper libraries.
- Done on 2026-05-12 in Batch 5: update geckodriver provisioning to `0.36.0` and remove runtime `webdriver_manager` dependency.
- Done on 2026-05-12 in Batch 6: add checked-in transitive constraints for both services and use them in Docker installs.
- Done on 2026-05-24 in Batch 12: move the main `am-core` Docker runtime and project metadata to Python 3.14.5.

Batch 3, Django 6 and CSP:

- Drop Python 3.11 support. Done in Batch 2.
- Add Django 6 CSP middleware and report-only policy. Done in Batch 10.
- Iterate CSP violations.
- Enforce CSP after reports are clean.

Batch 4, forum:

- Resolve `django-spirit`/Mistune.
- Upgrade or replace forum stack.
