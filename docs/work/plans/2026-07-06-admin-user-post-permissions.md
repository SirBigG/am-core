# Plan: Admin User Post Permissions

- Date: 2026-07-06
- Status: Draft
- Owner: Codex
- Related domain: Catalog information
- Related decisions: 2026-06-21 knowledge base and planning workflow

## Goal

Let administrators see staff status in the custom users admin, assign groups and user permissions from that page, and grant selected staff access to view and update only the posts they own.

## Non-Goals

This does not introduce full object-level permissions across the project, change public post ownership rules, or alter forum behavior.

## Current Understanding

`core.pro_auth.admin.UserAdmin` currently omits `is_staff` from the changelist and filters, and hides `groups` and `user_permissions` from the edit form. `core.posts.admin.PostAdmin` currently relies on standard Django model permissions, so staff with `posts.view_post` or `posts.change_post` can see all posts.

## Assumptions

Posts "they add" maps to `Post.publisher == request.user`. Staff who need to create posts in admin should still receive Django's standard `posts.add_post` permission; the new permission controls own-post view/change scope.

## Proposed Approach

Add a custom `posts.change_own_post` permission. In `PostAdmin`, users with global `view_post` or `change_post` keep all-post access. Staff with only `change_own_post` can open the posts changelist, see only their own posts, and view/change only their own post objects. When they save a post, keep ownership on the current user.

Update custom user admin fieldsets, filters, and horizontal permission widgets.

## Risks And Unknowns

Admin permissions are cached on user objects during a request, so tests should create permissions before checking access. Existing staff workflows that relied on changing the publisher while lacking global post change permission should become intentionally restricted.

## Test Strategy

Add targeted admin tests for user admin configuration, own-post queryset filtering, object-level view/change checks, and publisher enforcement. Run the relevant app tests.

## Documentation Updates

This plan records the permission behavior. No durable domain note update is needed unless product ownership rules change beyond admin scoping.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add or update tests where needed.
- [x] Implement the change.
- [x] Run targeted verification.
- [x] Update docs with new knowledge.
