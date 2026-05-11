# Package Upgrade Test Plan

Created: 2026-05-11

## Current Dependency Shape

The project currently uses `requirements.txt` and `forum_instance/requirements.txt` as the real dependency sources. `pyproject.toml` only declares the project metadata and Python range `>=3.12,<3.13`; it does not manage the runtime dependencies.

The main and forum Docker images use Python 3.12.13. Django 6 is technically possible for the Python runtime, but the forum stack still blocks a simple whole-repo Django 6 upgrade.

There is no lock file, hash file, or compiled constraints file. Before broader upgrades, we should add a reproducible dependency workflow, for example `pip-tools` with checked-in input and compiled output files.

## Security Findings

`pip-audit` was run on direct pinned main dependencies with `--no-deps` because the host Python 3.14 cannot build the currently pinned `Pillow==10.2.0`. It found vulnerabilities in:

- `Django==5.0.3`; minimum fixed line is at least `5.0.14`, but Django 5.0 is no longer the best target.
- `djangorestframework==3.15.1`; fix `3.15.2`.
- `Pillow==10.2.0`; full current fix target `12.2.0`.
- `requests==2.31.0`; fix at least `2.33.0`.
- `social-auth-app-django==5.4.0`; fix at least `5.6.0`.
- `python-jose==3.3.0`; fix `3.4.0`.
- `lxml==5.1.0`; fix `6.1.0`.

The forum full dependency audit found `mistune==0.8.4`, pulled by `django-spirit==0.14.3`, with CVEs fixed in `mistune==3.2.1`. `django-spirit==0.14.3` still pins `mistune==0.8.4` and requires `Django<6,>=4.2`, so the forum cannot move to Django 6 or fixed Mistune without replacing, forking, or patching Spirit. After Batch 2, forum audit still reports `CVE-2026-44708`, `CVE-2026-44896`, and `CVE-2026-44897` for `mistune==0.8.4`.

## Upgrade Feasibility

Recommended sequence:

1. Patch within the Django 5 line first: move main app to Django 5.2 LTS if compatible, and apply security updates for DRF, Pillow, requests, social auth, python-jose, and lxml.
2. Keep forum on Django 5.2-compatible dependencies while deciding how to handle `django-spirit`.
3. Add CSP in report-only mode before enforcing it. Django 6 has built-in `ContentSecurityPolicyMiddleware`, `SECURE_CSP`, `SECURE_CSP_REPORT_ONLY`, and nonce support. On Django 5.2, use `django-csp` or a small custom middleware if CSP is needed before the Django 6 jump.
4. Move main app to Django 6 only after the forum path is separated or solved. Python 3.11 support was intentionally dropped in Batch 2.

Known compatibility pressure:

- `Django==6.0.5` requires Python `>=3.12`.
- `django-spirit==0.14.3` requires `Django<6,>=4.2` and pins vulnerable `mistune==0.8.4`.
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

Verification commands run from `/Users/andriihots/Projects/am-dev`:

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
- `webdriver_manager==3.5.0` to `webdriver_manager==4.0.2`.
- `openpyxl==3.1.2` to `openpyxl==3.1.5`.
- `boto3==1.35.6` to `boto3==1.43.6`.
- `django-storages==1.14.4` to `django-storages==1.14.6`.
- Removed obsolete `ipaddress==1.0.23`; Python 3 provides `ipaddress` in the standard library.

Forum direct pin updates:

- `psycopg[c]==3.1.18` to `psycopg[c]==3.3.4`.
- `django-storages==1.14.4` to `django-storages==1.14.6`.
- `boto3==1.35.6` to `boto3==1.43.6`.

Verification commands run from `/Users/andriihots/Projects/am-dev`:

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
- The main image still downloads an old geckodriver `v0.30.0` manually. Selenium itself is current, but browser-driver provisioning should be revisited with the parser/browser automation path.
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

Verification commands run from `/Users/andriihots/Projects/am-dev`:

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
- `django_http2_push==0.0b2` is now pinned, but it is a beta package and should be reviewed during the reproducible dependency workflow.

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

- Implemented by `core.utils.security.ContentSecurityPolicyReportOnlyMiddleware`.
- Configured in `settings.settings.CONTENT_SECURITY_POLICY_REPORT_ONLY`.
- Intentionally allows current inline scripts/styles and known external assets so violations can be observed before any enforcement work.

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

- Done on 2026-05-12: boto3, django-storages, psycopg, daphne, selenium, webdriver_manager, openpyxl, phonenumbers, MarkupSafe, python-dateutil, xlrd, Python 3.12.13 Docker images, and removal of obsolete `ipaddress`.
- Done on 2026-05-12 in Batch 4: pin currently unpinned dev/test dependencies and update Django 5.2-compatible helper libraries.

Batch 3, Django 6 and CSP:

- Drop Python 3.11 support.
- Add Django 6 CSP middleware and report-only policy.
- Iterate CSP violations.
- Enforce CSP after reports are clean.

Batch 4, forum:

- Resolve `django-spirit`/Mistune.
- Upgrade or replace forum stack.
