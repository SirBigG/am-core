# Content attributes and filter schema API

The Content API now validates explicitly supplied post attributes and atomically rebuilds `PostAttributeValue` after create or attribute/category updates. Editorial-only PATCH requests preserve existing attributes and indexes. Post updates and schema writes serialize on the category so validation cannot race a schema mutation.

## Attribute contract

Supply a JSON object keyed by the selected category ID, containing field-key/value pairs. Unknown or inactive keys and choices, duplicate multiselect choices, string booleans, nonfinite numbers, reversed ranges and values outside field bounds/index precision return 400 without a partial post/index write. Numeric field precision is limited to the existing index's four decimal places. Omitted attributes are unknown; false and zero remain explicit values. An omitted attribute PATCH preserves current values. An explicit empty object clears current-category values while preserving historical other-category JSON.

Existing legacy data is not automatically rewritten or backfilled. Use the existing `rebuild_post_attribute_values` command as a separately authorized operational action when historical JSON needs indexing. Do not enable filtering on a previously unindexed used field through the schema API; review and rebuild its existing values first.

## Schema discovery and maintenance

- `GET /api/content/categories/<id>/schema/` returns the category ID, groups, fields, choices and deterministic schema checksum. Inactive fields and choices remain visible to integration operators.
- `GET/POST /api/content/attribute-groups/`, `attribute-fields/`, `attribute-choices/` provide paginated collections, filterable by their category or field relation.
- Integer-ID details support `GET/PUT/PATCH`. Deletes are unsupported; retire records with `is_active=false`.
- Token authentication is mandatory. Writes additionally require a staff user with the corresponding `posts.add_*` or `posts.change_*` model permission. Staff status alone does not authorize schema writes.
- Group/category consistency is checked. Used field semantics cannot change in place, and choice identity cannot be reassigned. Create a new field/choice and perform an explicit data migration instead of silently reinterpreting published characteristics.

## Acceptance protocol

Read the category schema, map reviewed facts to its exact keys/units/choices, preview changes, save through an authorized Content API action, GET the post, then verify its public filter results. An HTTP success or JSON read-back is insufficient without the derived filter query. Keep uncertain publication outcomes separate from retries.

## Verification

The focused Content API and category-attribute suite passed 29 tests against an isolated PostgreSQL database. It includes a post write followed by an attribute filter query, explicit false, invalid range rejection, metadata preservation, schema discovery, permission denial and used-field identity protection. Flake8 and diff whitespace checks passed for touched files.

The broader existing public-page suite has nine errors and one failure on an unchanged HEAD checkout under the same isolated settings: missing request context in canonical URL rendering and a sitemap count mismatch. These pre-existing failures are outside this API change. No deployment, production writes, schema creation, migrations or historical backfill were performed.
