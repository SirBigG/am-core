# Dependabot security dependency refresh

- Date: 2026-10-22
- Scope: `am-core` Python and frontend dependencies.
- Baseline: default branch `master`, commit `08351e891d0dce78d0239e4d7829eafdad5cc992`.

## Findings and selected versions

GitHub's authenticated Dependabot API reported 110 open alerts: 1 critical,
49 high, 52 medium and 8 low. These are alert instances, including repeated
advisories across `pyproject.toml` and `uv.lock`; they are not 110 distinct packages.
Registry audits also found advisories absent from that GitHub snapshot.

| Direct requirement | Before | After | Rationale |
| --- | --- | --- | --- |
| Django | 6.0.6 | 6.0.9 | Current security patch on the existing 6.0 line |
| Pillow | 12.2.0 | 13.0.0 | Full audit includes image decoder/encoder fixes beyond 12.3.0 |
| daphne | 4.2.1 | 4.2.3 | Security fixes available from 4.2.2 |
| djangorestframework | 3.17.1 | 3.18.3 | Includes 3.18.2 charset, Accept-header and token revocation fixes |
| social-auth-app-django | 5.9.0 | 6.0.1 | 5.9.0 requires vulnerable social-auth-core below 5.0 |
| python-jose | 3.5.0 | Removed | No Python source imports it; removes unpatched python-jose/ecdsa findings |

Targeted lock updates also cover PyJWT 2.15.1 (including the critical finding),
cryptography 50.0.2, pyOpenSSL 26.4.0, social-auth-core 5.0.2, OAuthLib 4.0.0,
SQLParse 0.6.0, pyasn1 0.6.4, urllib3 2.8.0, Autobahn 26.10.2,
ujson 5.13.0, certifi 2026.10.19 and msgpack 1.2.3. Removing python-jose also
removes unused rsa/ecdsa; Autobahn drops py-ubjson. Other direct pins remain unchanged.

`npm audit fix --package-lock-only --ignore-scripts` updates the existing allowed
dependency graph without changing `frontend/package.json`. Security-related
updates include fast-uri 3.1.9, browserslist 4.29.4, baseline-browser-mapping
2.11.31, PostCSS 8.5.31, postcss-selector-parser 7.1.7, SVGO 4.1.0,
nanoid 3.3.20 and source-map-js 1.2.2, together with required transitive updates.

## Social login compatibility

social-auth-app-django 6 requires POST for authentication initiation. Login and
comment social buttons now use a shared CSRF-protected POST form, preserving
the `next` destination. Provider callbacks retain the upstream callback routes.
The configured Google and Facebook providers are covered by tests that submit
the rendered forms, reject GET and missing CSRF, verify OAuth state generation,
and preserve `/forum/` destinations. Comment forms preserve the article path.

No installed third-party source is patched. Forum and Parser Studio dependencies
remain separate and unchanged.

## Remaining risk

The complete updated Python lock export has one remaining known advisory:
[GHSA-8pqf-f4m5-798g / CVE-2026-106454](https://github.com/advisories/GHSA-8pqf-f4m5-798g)
in Twisted 26.4.0, rated medium by GitHub. There is no patched PyPI release.
The affected code implements IMAP LIST/LSUB wildcard matching; this repository
does not import or serve Twisted IMAP. Twisted remains required by Daphne's
HTTP/WebSocket server. This is an exposure assessment, not an upstream fix or
an advisory dismissal; reassess when upstream publishes a patched release.

The pre-existing bundled CKEditor 4 warning remains a separate editor migration
risk. Package registry audits do not establish safety of bundled JavaScript.
The sibling forum's Spirit/Mistune risk is outside this change.

## Verification

- `uv lock`: successful targeted resolution.
- Full hashed lock export with all dependency groups, audited using pip-audit:
  before 136 reported advisory entries across 18 packages; after one advisory
  in Twisted. Counts include duplicate records returned by the audit service.
- `npm audit --package-lock-only`: before 6 high and 2 moderate vulnerable
  packages; after zero vulnerabilities.
- `npm ci --ignore-scripts`: clean installation succeeds, zero audit findings.
- `npm run build:static -- --output-path /tmp/am-core-security-static`: successful
  production build; existing Sass deprecation warnings remain. Temporary output
  avoids modifying checked-in compiled assets.
- Comparing the updated Python versions to every original Dependabot vulnerable
  range leaves only alert #205 (Twisted, medium). The original 15 npm alert
  instances are covered by the zero-finding npm audit. This is local range
  validation, not a GitHub alert-state update.
- `docker compose -f docker-compose.yml build core`: successful with Python 3.14.5.
- In that rebuilt image, Compose one-off containers passed `uv lock --check`,
  frozen all-group sync `--check` (no changes), `python -m pip check`, and Django
  system checks. Existing CKEditor and non-unique email warnings remain.
- Full PostgreSQL-backed `python manage.py test --settings=settings.test_settings
  --noinput`: **703 tests passed**, including the two new social-login regressions.
  The test database was destroyed normally; no application migrations were run
  against the persistent development database.
- Plain `flake8` is blocked by pre-existing gitignored helper scripts below
  `var/agents-work/`; `flake8 --extend-exclude var` passes for project code.
- `git diff --check`: passed. No commits, pushes or deployment performed.

Changes must reach the default branch and be rescanned before GitHub closes
alerts. Local audits do not establish production deployment or live social
provider acceptance. Deploy the rebuilt locked image through the normal release
process, run existing migrations, build/collect static assets, and smoke-test
Google/Facebook and forum SSO using real provider configuration. No deployment
is performed by this dependency refresh.

## Upstream references

- [Django October security release](https://www.djangoproject.com/weblog/2026/oct/06/security-releases/)
- [Pillow 13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
- [DRF release notes](https://www.django-rest-framework.org/community/release-notes/)
- [social-auth-app-django changelog](https://github.com/python-social-auth/social-app-django/blob/master/CHANGELOG.md)
- [social-auth-core changelog](https://github.com/python-social-auth/social-core/blob/master/CHANGELOG.md)
