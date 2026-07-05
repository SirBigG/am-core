# Plan: Registry Refresh From 2026 File

- Date: 2026-07-05
- Status: Completed
- Owner: Codex
- Related domain: Catalog information / registry reference data
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Update the registry parser so it can process the latest state registry spreadsheet and refresh the local database without deleting existing registry data. Provide an admin upload path so future refreshes can be queued from Django admin, plus a Django management command for processing.

## Non-Goals

- Do not remove existing registry rows before import.
- Do not remodel registry companies, categories, or varieties.
- Do not import newly available descriptive text into new model fields.
- Do not add Celery, RQ, or another external worker dependency in this pass.

## Current Understanding

The latest attached file is an OpenDocument spreadsheet with five sheets: active registry rows, excluded registry rows, applicants, owners, and maintainers. Compared with the older 2024 workbook, the active and inactive variety sheets include four additional columns in the middle of the row layout: selection number, certificate number, variety description, and EU/UPOV description. The old parser expected 38 active columns and 39 inactive columns, so it would misalign countries, companies, years, and agronomic attributes.

Django admin already exposes registry varieties, but there was no import view for uploading a fresh state registry workbook. Django 6 includes a Tasks framework, but the official documentation states that it does not provide the production worker mechanism, so this pass uses a small Django model plus management command instead of an external task backend.

## Assumptions

- Existing registry records should be preserved and updated by the current key of variety title plus category.
- The current `breeder` field continues to represent the spreadsheet's maintainer/supporter sheet.
- Publication links on existing registry varieties should remain untouched.

## Proposed Approach

- Normalize both old and new row layouts before constructing parser row tuples.
- Update active imports with upsert semantics, clearing excluded/unregister fields for active rows.
- Update inactive imports with upsert semantics, setting excluded/unregister fields and refreshing other imported fields.
- Keep company imports as upserts by company code.
- Add a Variety admin import page that accepts `.xlsx` and `.ods` files and queues a `RegistryImportJob`.
- Do not process imports from admin requests. Admin uploads only create queued jobs.
- Add a management command that claims pending jobs and runs the same no-delete upsert import.
- Add original country to the Variety admin list display as the fifth column.

## Risks And Unknowns

- The database has only first and second applicant/owner fields and one breeder field, while the file can contain six of each.
- The file contains descriptive text columns that do not currently map to dedicated registry model fields.
- Queued imports require the `run_registry_import_jobs` management command to be run manually or under a supervisor.
- Existing matching by title and category may not detect a renamed variety as the same record.

## Test Strategy

- Add focused tests for old/new row normalization.
- Add focused tests for active and inactive upsert behavior.
- Add focused tests for the admin import page and Variety admin column order.
- Add focused tests for queued job processing and failed-job rollback.
- Add focused tests that admin uploads queue jobs without processing them.
- Run `just test-target core.registry`.
- Verify post-import database counts and representative active/inactive rows.

## Documentation Updates

- Add a result artifact for the import and verification.
- Update catalog domain notes with current registry refresh behavior.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
