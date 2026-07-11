# Plan: Category Metadata Rich Content

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: Classification and taxonomy
- Related decisions: None

## Goal

Give category metadata the same rich-content authoring controls and public content styling as post bodies.

## Non-Goals

- Changing the metadata schema or stored HTML.
- Redesigning category headers or post content styles.

## Current Understanding

`MetaData.text` is a CKEditor rich-text field, but its base admin registration does not load the custom post editor assets that provide article blocks. Category templates render the HTML outside the shared `site-article-body` styling scope.

## Assumptions

The existing post editor assets and article-body CSS are the intended shared contract for trusted rich content.

## Proposed Approach

Register `MetaData` with a dedicated admin class that loads the posts CKEditor assets. Add `site-article-body` to metadata containers in post and registry category templates.

## Risks And Unknowns

Shared article typography may change spacing within the category hero; targeted template and admin tests will protect the intended integration points.

## Test Strategy

Verify that the metadata admin uses CKEditor and includes the post editor CSS/JavaScript, and that every category metadata template opts into `site-article-body`.

## Documentation Updates

This plan is sufficient; no new business rule or architectural decision is introduced.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
