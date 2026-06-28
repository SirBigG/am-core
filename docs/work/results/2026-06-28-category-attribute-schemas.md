# Result: Dynamic Category Attribute Schemas

- Date: 2026-06-28
- Status: Implemented
- Plan: `docs/work/plans/2026-06-28-category-attribute-schemas.md`

## Summary

Implemented a generic category attribute schema foundation for posts.

The apple-specific JSON field is now a generic `Post.category_attributes` payload. Values are stored by category id so old category-specific data is preserved when a post changes rubric. Public filtering uses a separate `PostAttributeValue` index that is rebuilt for the current post category only.

## What Changed

- Added schema models:
  - `CategoryAttributeGroup`
  - `CategoryAttributeField`
  - `CategoryAttributeChoice`
  - `PostAttributeValue`
- Added field types for select, multiselect, integer, decimal, interval range, and boolean.
- Added admin management for schema groups, fields, choices, and indexed values.
- Replaced the hardcoded apple admin form fields with schema-driven dynamic fields.
- Added interval parsing for exact, min-only, max-only, and min/max values.
- Added public attribute filters to the `А-Я` category page only.
- Excluded internal/private fields and choices from public filters.
- Added a migration that renames `apple_attributes` to `category_attributes`, wraps existing values by category id, and seeds the current apple variety schema.

## Verification

- `just test-target core.posts`
- `docker compose --project-directory /Users/andriihots/Projects/am-dev/am-core/.. exec core ./manage.py makemigrations --check --dry-run`
- `docker compose --project-directory /Users/andriihots/Projects/am-dev/am-core/.. exec core flake8 core/posts/admin.py core/posts/category_attributes.py core/posts/category_attribute_filters.py core/posts/models.py core/posts/views.py core/posts/tests/test_admin.py core/posts/tests/test_category_attributes.py core/posts/tests/test_views.py core/utils/tests/factories.py core/posts/migrations/0030_category_attribute_schemas.py`
- `docker compose --project-directory /Users/andriihots/Projects/am-dev/am-core/.. exec core uv tool run djlint --profile=django --lint core/posts/templates/posts/list_order.html`

## Notes

The full project template lint still has existing unrelated failures in older templates. The touched template passed scoped lint.
