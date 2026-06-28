# Plan: Dynamic Category Attribute Schemas

- Date: 2026-06-28
- Status: Implemented
- Owner: Andrii / Codex
- Related domain: Classification and taxonomy, catalog information
- Related decisions: 2026-06-21 knowledge-base foundation

## Goal

Create a reusable way to configure category-specific post attributes and use those attributes as public filters on concrete category pages.

The first target is to replace the hardcoded apple variety attributes with a generic system that can also describe other concrete categories, for example apple illnesses, chicken breeds, or any future category where posts need structured fields.

## Non-Goals

- Do not redesign the full category tree or change how posts are assigned to categories.
- Do not apply schemas from parent categories in the first version. Schemas should belong to concrete categories.
- Do not replace full-text search or all existing category list behavior.
- Do not add schema filters to the paginated `Список` page in the first version.
- Do not build filters for adverts, companies, diary records, or registry records until those domains explicitly need the same schema system.
- Do not support arbitrary unvalidated free-form filters in the first version.

## Current Understanding

- `Category` is the shared MPTT taxonomy model in `core.classifier`.
- `Post` belongs to one concrete category through `Post.rubric`.
- The current apple variety work stores structured values in `Post.apple_attributes`.
- Apple attributes are currently hardcoded in `core/posts/apple_attributes.py` and wired directly into `AdminPostForm`.
- Public category pages currently have two views:
  - `PostListView` for the alphabetic catalog at `/<parent>/<child>/`.
  - `PostList` for the paginated list at `/<parent>/<child>/list/`.
- The alphabetic catalog already has a simple country filter, which is a good place to integrate standard schema filters.

## Assumptions

- Each schema group and field belongs to exactly one concrete category.
- A concrete category can have many schema groups and many fields.
- Field keys should be stable once posts use them. Labels can change, but keys should not be casually renamed.
- Editors will configure schemas in Django admin.
- Public filters should appear only on the `А-Я` category view in the first version.
- Public filters should appear only when at least one active post in that category has a public value for the field.
- For choice fields, public options should appear only when at least one active post uses that option.
- For range fields, posts need optional interval values that can be queried with minimum and maximum filter inputs.
- Category changes can happen often, so old structured data should be preserved even when it no longer applies to the current category.

## Proposed Approach

Add generic schema models for category attributes:

- `CategoryAttributeGroup`
  - `category`
  - `title`
  - `description`
  - `is_active`
  - `sort_order`
- `CategoryAttributeField`
  - `category`
  - `group`
  - `key`
  - `label`
  - `field_type`
  - `help_text`
  - `unit`
  - `is_active`
  - `is_required`
  - `is_filterable`
  - `is_public`
  - `sort_order`
  - numeric display metadata such as decimal places for decimal/range fields
  - validation metadata such as minimum and maximum values when needed
- `CategoryAttributeChoice`
  - `field`
  - `value`
  - `label`
  - `is_active`
  - `is_public`
  - `sort_order`

Supported first-version field types:

- `select`
- `multiselect`
- `integer`
- `decimal`
- `range`
- `boolean`

Integer and decimal behavior should be configured per field. For example, eggs per year should display without decimals, while other measurements can allow and display decimal values.

Range values should be stored as an interval with optional endpoints:

- exact value: `{ "min": 220, "max": 220 }`
- maximum-only value, for example "up to 220 eggs per year": `{ "max": 220 }`
- minimum-only value, for example "from 120 cm": `{ "min": 120 }`
- interval value, for example "100-150 g": `{ "min": 100, "max": 150 }`

Schema metadata can provide the unit label, such as `g`, `kg`, `cm`, or `eggs/year`, plus the display precision.

Keep one canonical JSON object on `Post` for the editor-facing values. Because the current branch already has `apple_attributes`, rename or replace it with a generic field such as `category_attributes` before merge.

The JSON payload should preserve values by schema category instead of keeping only the current category values. That lets editors change a post category without silently losing structured data. A rough shape:

```json
{
  "category_id": {
    "field_key": "value"
  }
}
```

Only the current `Post.rubric` category should contribute to public filter indexes. Old values for previous categories can remain visible in a collapsed admin-only "stored category attributes" view, similar in spirit to preserving source/original data for editors.

Add a query-friendly index model for public filtering:

- `PostAttributeValue`
  - `post`
  - `category`
  - `field`
  - `choice`
  - `value_text`
  - `value_number`
  - `value_boolean`

The JSON field remains the canonical editable payload. `PostAttributeValue` is rebuilt from that JSON when a post is saved. This avoids depending on complex JSON queries for available filter values, counts, and range filters.

Update Django admin:

- Manage schema fields and choices from admin, preferably on or near the category admin.
- Replace apple-specific form fields with fields generated from the selected category schema.
- Preserve the current apple schema by seeding `sorty-yablun` from the existing hardcoded constants.
- When a post changes category, do not delete old JSON values.
- When a post changes category, rebuild indexed values only for the selected category so old values do not leak into public filters.
- Show hidden/internal fields in admin, but exclude them from public filters and public templates.

Update public category filters:

- Build a filter definition from active, filterable schema fields for the current concrete category.
- Compute available options from active posts through `PostAttributeValue`.
- Hide fields that have no public values in the current category.
- Exclude fields and choices where `is_public=False`.
- Apply filters with predictable query params:
  - `attr_<key>=value` for `select`
  - repeated `attr_<key>=value` params for `multiselect`
  - `attr_<key>_min=...` and `attr_<key>_max=...` for numeric or range fields
  - `attr_<key>=1` / `attr_<key>=0` for boolean fields
- Preserve existing filters such as `country`, ordering, and pagination links.
- Apply schema filters only to the `А-Я` category page in the first version.

## Risks And Unknowns

- JSON-only filtering would become difficult and slow, especially for multi-choice fields and ranges. The index model reduces that risk.
- Renaming schema keys after posts use them can orphan values. We should treat keys as immutable in admin after creation or add an explicit migration action later.
- Deleting choices can break historical post values. Prefer deactivating choices over hard deletion.
- Changing a post category needs clear indexing rules so old category-specific values are preserved for editors but do not leak into filters.
- Range fields must handle partial intervals, because some content has only a maximum value while other content has a full minimum and maximum range.
- Internal-only fields and choices need careful naming in admin so editors understand they are saved but not public.
- Public filter UI must stay compact on mobile and tablet, because category pages now intentionally use the mobile layout up to tablet widths.

## Test Strategy

- Model tests for schema validation:
  - unique field keys per category
  - valid choices for select and multiselect fields
  - numeric/range value normalization
  - range values with only `min`, only `max`, exact value, and full interval
- Admin form tests:
  - schema fields appear for a category with a schema
  - fields do not appear for categories without schemas
  - saved posts write normalized `category_attributes`
  - saved posts rebuild `PostAttributeValue`
  - changing category preserves old JSON values
  - changing category removes stale indexed values
  - hidden/internal fields save in admin but do not appear as public filters
- Migration/seed tests:
  - existing apple attribute configuration is represented as category schema rows
  - existing post values migrate from `apple_attributes` to the generic field if data exists
- View tests:
  - no filter block appears when no schema values exist
  - select and multiselect options show only values used by active posts
  - hidden/internal fields and choices are excluded from public filters
  - range filters apply min/max correctly
  - filters compose with `country`, ordering, and pagination
  - schema filters appear on `А-Я` and not on `Список` in the first version
- Visual/browser checks:
  - category filter block works on desktop
  - tablet uses the same layout behavior as mobile
  - long Ukrainian labels do not overflow filter controls

## Documentation Updates

- Update `docs/business/domains/classification-and-taxonomy/README.md` with the new rule that concrete categories can own structured post schemas.
- Add an engineering result note after implementation with the migration path, verification results, and follow-up decisions.
- Update `AGENTS.md` only if the workflow for category/schema changes needs special agent guidance.

## Implementation Checklist

- [x] Confirm first-version range semantics.
- [x] Confirm first-version field types beyond range.
- [x] Confirm filters should start on `А-Я` only.
- [x] Confirm old category attribute data should be preserved on category changes.
- [x] Add schema and indexed value models.
- [x] Add migrations for generic post attributes and apple schema seed data.
- [x] Replace apple-specific admin form wiring with schema-driven form generation.
- [x] Add index rebuild service for post attribute values.
- [x] Add public filter builder for concrete category pages.
- [x] Update category templates to render schema filters.
- [x] Add focused model, admin, migration, and view tests.
- [x] Run targeted tests and template lint for touched templates.
- [x] Update domain docs and write a result artifact.
