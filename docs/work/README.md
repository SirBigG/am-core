# Work Artifacts

This folder collects planning and result artifacts produced during delivery work.

Use this area for documents that explain how a specific task was planned, executed, verified, or summarized. Keep durable business knowledge, engineering decisions, architecture notes, and domain references in the main `docs/business/` and `docs/engineering/` folders.

## Structure

- `plans/` - implementation plans, upgrade plans, migration plans, and other before-work planning documents.
- `results/` - implementation results, investigation outputs, verification summaries, audit outputs, and other after-work records.

## Working Rule

Plans and results may be referenced from durable docs, but they should not replace durable docs.

When a work artifact discovers lasting knowledge, update the relevant domain note, decision record, dependency note, security note, or testing note.

## Naming

Use dated filenames:

```text
YYYY-MM-DD-short-topic.md
```

For related plan/result pairs, reuse the same short topic:

```text
plans/2026-06-21-company-profile-cleanup.md
results/2026-06-21-company-profile-cleanup.md
```
