# Category Hub deletion permissions and release verification

Date: 2026-10-17. Base revision inspected: `74c3a4a`; this follow-up is a local
source change, not a production deployment record.

## Failure and correction

CategoryHubSection has no standalone ModelAdmin. Django's related-object
deletion collector therefore did not require its delete permission when a
registered parent cascaded to those rows. The pre-deployment probe reproduced a
staff user deleting a populated hub with `delete_categoryhub` but without
`delete_categoryhubsection`. The content API already guarded that operation.

`core/classifier/hub_permissions.py` now supplies the shared child-reference
deletion check. Admin applies it to:

- Individual and standard bulk CategoryHub deletion, including confirmed POSTs.
- CategoryHub deletion through a Category form's inline. The delete control is
  hidden when child permission is absent; a separate save-time check protects
  against a stale or overridden UI decision and rolls back the category edit.
- Category/subtree deletion, including confirmed MPTT bulk actions and mixed
  selections. Both hub ownership and section targets are checked: deleting a
  referenced category can remove another branch's Hub-section references.

The API calls the same policy. Existing GuideSectionArticle visibility/deletion
checks remain in place. Ordinary parent-delete permissions are still required;
the new check supplements them. Empty hub deletion remains permitted without
child-delete permission. Configuration deletion preserves referenced source
categories and articles; actual category deletion retains its existing broader
cascade behavior.

## Regression coverage

Ten added restricted-staff tests verify denied/allowed single and bulk hub
deletion, mixed bulk selection atomicity, empty hubs, hidden and forged inline
controls, inline transaction rollback, owner/ancestor taxonomy deletion,
cross-branch target cascades and unrelated category deletion. Existing API
permission tests verify equivalent child-delete requirements.

Three stale assertions were corrected without changing public behavior:

- Article aliases must permanently redirect to the canonical article URL before
  checking the destination's canonical/social metadata.
- The sitemap index includes the Agromarket sitemap alongside main, adverts,
  news and forum destinations. The test now checks the complete destination set.
- Crop-scope reset-link assertions compare semantic HTML rather than whitespace
  introduced by template formatting.

The full flake8 command originally included ignored editorial run scripts.
`content_refresh_runs/` is now excluded in `.flake8`, matching its existing Git
and Docker exclusions. Application lint remains enabled and those local scripts
were not modified.

## Verification

- Focused permission/admin/API run: 27 tests passed.
- Affected API/post/guide/classifier/company run: 355 tests passed in 19.098s.
- No model migration drift; local migration plan has no pending operations.
- Frontend production asset build succeeds (existing Sass deprecation warnings).
- Static collection dry run succeeds: 3,615 unmodified assets.
- Complete Django suite on a fresh test database: **646/646 passed** in 19.748s.
- Full-project flake8 and `git diff --check`: passed.

The initial full run with `--keepdb` encountered an unrelated missing legal-page
seed in the reused test database: earlier transactional migration tests had
flushed migration-created rows. Running the complete suite with a fresh test
database verified the legal-page seeding and all other tests without changing
the legal-page code or its assertions. Reproduce the final run from the workspace:

```bash
docker compose exec -T core python manage.py test --settings=settings.test_settings --noinput
docker compose exec -T core flake8
docker compose exec -T core python manage.py makemigrations --check --dry-run
docker compose exec -T core npm --prefix frontend run build:static
docker compose exec -T core python manage.py collectstatic --dry-run --noinput -i node_modules --settings=settings.dev
```

Final feature review found no remaining blocker in the deletion fix. This is
source/local verification; the target-server acceptance steps below remain.

`check --deploy --settings=settings.settings` completed in the local environment
with seven warnings: legacy CKEditor 4, non-unique login email, and local HSTS,
SSL redirect, secret-key strength, secure session-cookie and secure CSRF-cookie
settings. Local credentials/settings are not production acceptance evidence.
These warnings were not suppressed or changed by the permission fix.

## Release handoff

Package the final reviewed source, including the new permission module/tests and
documentation. No commit, push, target-server change or production permission
grant was performed by this follow-up.

In the target release runtime, use the actual production settings and existing
deployment procedure. Verify backup/release identity and run `check`,
`check --deploy`, `migrate --plan`, then apply approved migrations before serving
new-code workers. The permission fix adds no schema migration; the overall hub
feature still requires classifier 0016/0017 and its Guide Hub foundation.
Build/collect static files and verify `migrate --check` after migration.

Review the main crop page, its canonical URL, known article URLs, scoped market
and seller destinations, and denied deletion with the intended restricted staff
role. Configure real production hub references separately: application deployment
does not copy local database configuration. Disable a hub to roll back its
presentation while preserving curation. Server settings, migration state, proxy
behavior and live page acceptance require checks on the target environment.
