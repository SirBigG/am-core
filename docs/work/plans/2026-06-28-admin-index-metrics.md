# Plan: Admin Index Metrics

- Date: 2026-06-28
- Status: Implemented
- Owner: Andrii / Codex
- Related domain: Admin operations
- Related decisions: 2026-06-21 knowledge base and planning workflow

## Goal

Show useful last-30-day operational metrics on the Django admin index: adverts, posts, users, and latest feedback descriptions.

## Non-Goals

- Building a separate analytics dashboard.
- Adding charting or external tracking.
- Changing model behavior or public site pages.

## Current Understanding

- The admin index can be extended with `templates/admin/index.html`.
- Adverts use `Advert.created`.
- Posts do not have a creation timestamp; `Post.publish_date` is the closest field for "new posts" in an admin period metric.
- Users use `User.date_joined`.
- Feedback uses `Feedback.created` and should be shown as recent descriptive entries rather than only a number.

## Assumptions

- The period is the last 30 calendar days from `timezone.now()`.
- Metrics should respect Django model view permissions for the current staff user.
- Counts should be cheap aggregate queries and feedback should be limited to a small recent list.

## Proposed Approach

- Add a template tag that builds a permission-aware admin dashboard context.
- Override the Django admin index template to render metric cards above the app list.
- Style the cards with admin CSS variables so light/dark admin themes continue to work.
- Add focused tests for the metric window, permissions, and template rendering.

## Risks And Unknowns

- "New posts" may later need a real creation field if publish date is not the desired operational meaning.
- Staff users with partial permissions should only see the metrics they are allowed to view.

## Test Strategy

- Unit-test the dashboard context builder.
- Render `/admin/` with a superuser and assert the metrics and latest feedback appear.
- Run Django system check.

## Documentation Updates

- This plan documents the implementation decision.

## Implementation Checklist

- [x] Confirm fields and permissions.
- [x] Add admin dashboard context builder/template tag.
- [x] Override admin index template.
- [x] Add focused tests.
- [x] Run targeted verification.
