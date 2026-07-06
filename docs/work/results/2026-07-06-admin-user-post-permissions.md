# Result: Admin User Post Permissions

- Date: 2026-07-06
- Plan: `docs/work/plans/2026-07-06-admin-user-post-permissions.md`

## Summary

Custom users admin now shows and filters by `is_staff`, and exposes `groups` and `user_permissions` on the user edit page.

Posts now have a custom `posts.change_own_post` permission. Staff with that permission can access the posts admin changelist, view only posts where they are the `publisher`, and change only those posts. Staff with standard global `posts.view_post` or `posts.change_post` permissions keep full post admin access.

## Verification

- `just test-target core.posts.tests.test_admin`: passed.
- `just test-target core.pro_auth.tests.test_admin`: passed.
- `docker compose --project-directory /Users/andriihots/Projects/am-dev/am-core/.. exec core flake8 core/pro_auth/admin.py core/pro_auth/tests/test_admin.py core/posts/admin.py core/posts/models.py core/posts/tests/test_admin.py core/posts/migrations/0032_post_change_own_post_permission.py`: passed.
- `just makemigrations posts --check --dry-run`: passed with no changes detected.

## Notes

An initial full `core.posts` test run also exposed an existing `core.posts.tests.test_views.PostListTests.test_child_list_grouped_opens_filter_panel_when_filter_is_active` failure unrelated to the admin permission change.
