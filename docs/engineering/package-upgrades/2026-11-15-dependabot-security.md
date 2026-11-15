# Dependabot security follow-up

- Date: 2026-11-15
- Scope: am-core Python and frontend dependencies.
- Local baseline: `feature/potato-agromarket-redesign`.
- GitHub default branch at inspection: `master`, `5ae543dbd8937c2a1af1e181604966f789098284`.

## Findings and selected versions

The authenticated GitHub API returned 84 open alert instances: 6 critical,
47 high, 27 medium and 4 low. Most concern packages already updated or removed
on this local branch by the October refresh. Alert state on GitHub is distinct
from the dependencies in this checkout.

| Package | Before | After |
| --- | --- | --- |
| social-auth-app-django | 6.0.1 | 7.2.0 |
| social-auth-core | 5.0.2 | 6.2.0 |
| Twisted | 26.4.0 | 26.10.0 |
| pyasn1 | 0.6.4 | 0.6.5 |
| OAuthLib | 4.0.0 | 4.0.1 |
| serialize-javascript | 7.0.6 | 7.1.4 |

Only the Django social-auth integration changes a direct Python pin. Version
6.0.1 constrains social-auth-core below 6; 7.2.0 permits the patched 6.2.0
release. The custom partial pipeline step no longer requires the removed
`request` argument. It does not use the request. Future pipeline steps that
need it should access `strategy.request`.

The upstream OIDC nonce fix is described in
[GHSA-h2r5-x5m7-3935](https://github.com/advisories/GHSA-h2r5-x5m7-3935).
Compatibility changes are documented in the
[social-app-django changelog](https://github.com/python-social-auth/social-app-django/blob/7.2.0/CHANGELOG.md)
and [social-core changelog](https://github.com/python-social-auth/social-core/blob/6.2.0/CHANGELOG.md).

The stable [Twisted 26.10.0 release](https://github.com/twisted/twisted/releases/tag/twisted-26.10.0)
resolves the known Twisted findings, including the IMAP advisory retained in
the October report. That report's remaining-risk assessment is historical.
No advisory is dismissed or suppressed. Forum and Parser Studio dependencies
remain separately owned.

## Verification

- Every captured GitHub affected-version range was compared against the new
  Python and npm lockfiles: none of the 84 alert instances still applies.
  Removed packages count as absent; this does not change GitHub alert state.
- Full all-group hashed Python lock export audited with pip-audit: zero known
  vulnerabilities. npm lock audit and clean `npm ci --ignore-scripts`: zero
  vulnerabilities.
- Production frontend build to temporary output passed; existing Sass warnings
  remain. Checked-in compiled assets were not regenerated.
- Core Docker image rebuilt successfully. In a one-off container, `uv lock
  --check`, frozen all-group sync `--check`, `pip check` and Django system checks
  passed. Existing CKEditor and non-unique email warnings remain.
- Full PostgreSQL-backed Django/API suite: 720 tests passed. The final auth
  suite, including the additional existing Google account regression: 40 tests
  passed. Project `flake8 --extend-exclude var` and `git diff --check` passed.
- The verified image uses Python 3.14.5. A concurrent, separately made
  Dockerfile update to Python 3.14.10 was observed after this build; these
  results do not verify that newer base image. A concurrent application version
  bump to 0.1.0 was preserved and synchronized into the lockfile; final lock,
  frozen sync and runtime dependency checks passed afterward.

## Release requirements

Build and deploy the locked core image, run the standard Django migrations,
and deploy all core workers together. social-auth-app-django adds identifier
metadata/backfill, bounded legacy OIDC nonces and a nonce timestamp index
through upstream migration `0022_nonce_timestamp_index`. Review historical
empty or missing social identifiers before release: the upstream UID
constraint can reject invalid existing rows. Custom historical identifier
settings require review of `SOCIAL_AUTH_OLD_ID_KEYS` before migration.

Google now uses the verified UserInfo `sub` identifier. Existing email-based
associations are migrated by upstream authentication using stored identifier
evidence. Do not bulk-delete or recreate social accounts. Newly started Google
callback tests cover both new users and existing email-based associations.
In-progress OAuth2/OpenID flows from the previous version must restart after
the coordinated upgrade; older workers cannot read the new partial encoding.
Smoke-test Google/Facebook callbacks and forum SSO with real provider
configuration after rollout. No persistent development or production database
migration, push, or deployment is performed by this change.

GitHub closes alerts only after the fixes reach the scanned default branch
and its dependency graph is refreshed. Zero registry findings do not cover
bundled CKEditor 4, whose existing migration risk remains separate, or prove
live provider acceptance.
