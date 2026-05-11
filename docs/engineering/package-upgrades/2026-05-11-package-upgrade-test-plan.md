# Package Upgrade Test Plan

Created: 2026-05-11

## Current Dependency Shape

The project currently uses `requirements.txt` and `forum_instance/requirements.txt` as the real dependency sources. `pyproject.toml` only declares the project metadata and Python range `>=3.11,<3.13`; it does not manage the runtime dependencies.

The main Docker image uses Python 3.12.2, so Django 6 is technically possible for the container build, but adopting it would require dropping Python 3.11 support in `pyproject.toml`.

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

The forum full dependency audit found `mistune==0.8.4`, pulled by `django-spirit==0.14.3`, with CVEs fixed in `mistune==3.2.1`. `django-spirit==0.14.3` still pins `mistune==0.8.4` and requires `Django<6,>=4.2`, so the forum cannot move to Django 6 or fixed Mistune without replacing, forking, or patching Spirit.

## Upgrade Feasibility

Recommended sequence:

1. Patch within the Django 5 line first: move main app to Django 5.2 LTS if compatible, and apply security updates for DRF, Pillow, requests, social auth, python-jose, and lxml.
2. Keep forum on Django 5.2-compatible dependencies while deciding how to handle `django-spirit`.
3. Add CSP in report-only mode before enforcing it. Django 6 has built-in `ContentSecurityPolicyMiddleware`, `SECURE_CSP`, `SECURE_CSP_REPORT_ONLY`, and nonce support. On Django 5.2, use `django-csp` or a small custom middleware if CSP is needed before the Django 6 jump.
4. Move main app to Django 6 only after Python 3.11 support is intentionally dropped and the forum path is separated or solved.

Known compatibility pressure:

- `Django==6.0.5` requires Python `>=3.12`.
- `django-spirit==0.14.3` requires `Django<6,>=4.2` and pins vulnerable `mistune==0.8.4`.
- `social-auth-app-django==5.9.0` requires `Django>=5.2`.
- `django-autocomplete-light==4.0.0` requires `Django>=5.2`.

## Current Test Coverage Shape

The repo has about 25 test files:

- Main app: 19 test files, roughly 2,830 lines.
- API app: 5 test files, roughly 307 lines.
- Forum app: 9 tests covering SSO redirects and the forum user sync pipeline.

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

- Pagination shape.
- Filtering and search parameters.
- Authentication-required endpoints.
- Create/update/delete permissions.
- Serializer output fields for posts, events, services, classifiers, and auth endpoints.
- Error status and validation response shape.

Exit criteria:

- `djangorestframework` upgrades can be verified by response contracts, not just status codes.

### Step 5: File, Image, And Storage Tests

Add tests for:

- Image upload and thumbnail/image URL handling.
- CKEditor rich text fields and upload paths.
- `core.utils.storage.StaticFilesStorageWithoutVersion`.
- Local media handling under test settings.
- S3 storage settings construction in `settings/live.py` and forum S3 settings without real AWS calls.

Exit criteria:

- Pillow, django-storages, boto3, and CKEditor updates are covered.

### Step 6: Security Header And CSP Tests

Before enforcing CSP:

- Add tests that `SecurityMiddleware` headers are present.
- Add report-only CSP tests for public pages.
- Inventory inline scripts/styles and external assets currently used by templates.
- Add tests for any CSP nonce/context processor behavior if using Django 6 or `django-csp`.
- Verify pages using Bootstrap CDN, CKEditor, reCAPTCHA, and admin assets receive a policy that does not break rendering.

Exit criteria:

- CSP can start in report-only mode without blocking core pages.
- Enforcement can be done page group by page group.

### Step 7: Forum Dependency Decision

Before upgrading forum dependencies:

- Add minimal forum smoke tests: home, topic list, topic detail, login start, logout, profile update redirect.
- Decide between three paths for `django-spirit`:
  - Keep Spirit temporarily and accept Django `<6` for the forum.
  - Fork/patch Spirit to remove the vulnerable Mistune pin and test parser behavior.
  - Replace Spirit with another maintained forum approach.

Exit criteria:

- The vulnerable Mistune dependency has a deliberate mitigation path.
- Forum and main-app Django versions are intentionally coupled or intentionally separated.

## Suggested Upgrade Batches

Batch 1, security patch without framework jump:

- Django to latest safe 5.0 patch or preferably 5.2 LTS.
- DRF, requests, python-jose, social-auth-app-django, Pillow, lxml.

Batch 2, ecosystem cleanup:

- boto3, django-storages, psycopg, daphne, selenium, webdriver_manager, openpyxl, phonenumbers, MarkupSafe.
- Remove obsolete `ipaddress` on Python 3.
- Pin currently unpinned dev/test dependencies.

Batch 3, Django 6 and CSP:

- Drop Python 3.11 support.
- Add Django 6 CSP middleware and report-only policy.
- Iterate CSP violations.
- Enforce CSP after reports are clean.

Batch 4, forum:

- Resolve `django-spirit`/Mistune.
- Upgrade or replace forum stack.
