# Result: Registry Refresh From 2026 File

- Date: 2026-07-05
- Status: Completed
- Related plan: `docs/work/plans/2026-07-05-registry-refresh-2026-file.md`

## Summary

Updated the registry parser to accept the latest 2026 spreadsheet layout and refreshed the local database from the attached file without deleting existing rows. Added a Django admin upload flow that queues future registry refreshes, plus a Django management command for processing.

## Source File

- User-provided attachment: `/Users/andriihots/Downloads/file.ods`
- Converted local import copy: `media/registry_2026_06_29.xlsx`
- Active sheet: `Реєстр_29_06_2026`
- Inactive sheet: `Виключені_з_реєстру`

## Changes Made

- Added parser row normalization for both the older 2024 layout and the newer 2026 layout.
- Added fields for selection number, certificate number, variety description, EU/UPOV description, and variety status in parser row tuples.
- Changed company import to update existing companies by code instead of only skipping them.
- Changed active variety import to update existing varieties and clear `excluded`, `unregister_date`, and `unregister_year`.
- Changed inactive variety import to update existing varieties and set exclusion metadata.
- Added direct `.ods` parsing with the standard library, so the state registry file can be uploaded without a manual XLSX conversion.
- Added a `Variety` admin import page that accepts `.xlsx` and `.ods` files and creates a `RegistryImportJob`.
- Kept admin uploads queue-only so imports do not run inside admin requests.
- Added `run_registry_import_jobs`, a Django management command that processes queued registry import jobs without Celery/RQ or another external worker dependency.
- Guarded command processing so a pending job is not claimed while another registry import is already running.
- Added `RegistryImportJob` admin visibility for pending, running, succeeded, and failed imports.
- Added `original_country` as the fifth visible column in the `Variety` admin list.
- Made local/admin workbook imports transactional so a mid-import failure rolls back earlier sheet writes.
- Removed uploaded-workbook imports from the mutable module-level parser path to avoid concurrent admin uploads cross-reading files.
- Made importer sheet counts visible in the admin success summary.
- Accepted ISO date strings emitted by ODS date cells.

## Database Refresh

Before import:

- Companies: 934
- Varieties: 24,192
- Categories: 552
- Excluded varieties: 9,813

After import:

- Companies: 1,034
- Varieties: 26,449
- Categories: 563
- Active varieties: 10,064
- Excluded varieties: 16,385

Duplicate checks after import:

- Duplicate company codes: 0
- Duplicate variety title/category keys: 0

## Verification

- `just test-target core.registry` passed.
- `just flake` passed.
- The admin import page imported a representative uploaded workbook in tests.
- Regression tests cover import result counts, rollback on a later-sheet failure, and ISO ODS date parsing.
- Regression tests cover queued admin uploads, successful job processing, and failed job status/error recording.
- Regression tests cover that admin uploads queue jobs without processing registry rows.
- Regression tests cover that the command does not start a second pending import while another import is already running.
- The direct ODS reader was smoke-tested against `/Users/andriihots/Downloads/file.ods`; it found five sheets, 10,124 active rows, and 16,426 excluded rows.
- Sample active row `Бержерон 1` imported with application number `24256002`, registration year `2024`, active state, Ukrainian origin/applicant country, and applicant/owner code `3218`.
- Sample inactive row `Авіатор` imported with unregister date `2016-01-04`, excluded state, direction `універс.`, and ripeness group `пізн.` from the latest file.

## Follow-Up

- Decide whether registry descriptive text from the new spreadsheet should be stored in `Variety.description` or a dedicated structured model.
- Decide whether applicant/owner/maintainer fields beyond the first two should be modeled.
- Decide whether to run `run_registry_import_jobs --poll` under the production process supervisor, use admin-triggered processing only, or keep both options available.
