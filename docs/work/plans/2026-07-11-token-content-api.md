# Plan: Token-authenticated content API

- Date: 2026-07-11
- Status: Complete
- Owner: Codex
- Related domain: Catalog Information; Classification And Taxonomy
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Provide token-authenticated endpoints that let an integration read the active category tree and countries, list and filter posts, create posts owned by the token user, and let staff-token editors update existing posts.

## Non-Goals

- Replacing or changing the behavior of the existing public and user-facing API endpoints.
- Adding a second API-key model or credential format.
- Adding photo upload support to this JSON-focused integration contract.
- Allowing non-staff token owners to update posts.

## Current Understanding

- Django REST Framework token authentication is already configured and used by parser-worker APIs with `Authorization: Token <key>`.
- Categories form an MPTT tree and expose `value` as their human-readable title.
- Posts belong to a publisher and category, optionally belong to a country, and include editorial metadata and photos.
- The existing category tree endpoint only includes two levels, and the existing post serializers are too sparse or implement user-category/photo behavior that does not fit this integration.

## Assumptions

- “API key” means the existing DRF token owned by a user.
- Read endpoints should return shared catalog data, while writes should derive and enforce ownership from the authenticated token.
- Rubric and country filters should support either database ID or slug.
- Inactive categories should not appear in the integration category tree.

## Proposed Approach

- Add a separate `/api/content/` endpoint group protected explicitly by token authentication and `IsAuthenticated`.
- Recursively serialize the active category tree with `id`, `slug`, `title`, and `children`.
- Serialize countries with identifiers and titles.
- Add a detailed post serializer and a page-number paginator with a configurable `page_size` capped at 100.
- Support rubric and country query filters by ID or slug.
- Add create operations owned by the token user and staff-only update operations across publishers; never accept `publisher` from request data.

## Risks And Unknowns

- Existing tokens have no dedicated content-API permission, so any valid user token can use this contract.
- Rich-text fields are returned and accepted as stored HTML.
- Large post bodies and photo lists can make pages sizable even with the 100-record cap.

## Test Strategy

- Verify every endpoint rejects missing credentials and accepts a valid token.
- Verify recursive category output and inactive-category exclusion.
- Verify country output.
- Verify post filtering, detailed output, default pagination, custom page size, and the maximum cap.
- Verify creation assigns the token owner and validates required/optional relations.
- Verify staff updates across publishers, publisher cannot be overridden, and non-staff tokens receive `403` on detail/update.

## Documentation Updates

- Record the API contract and security/ownership rules in a result artifact after verification.
- Update catalog and taxonomy domain notes with confirmed integration behavior.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
