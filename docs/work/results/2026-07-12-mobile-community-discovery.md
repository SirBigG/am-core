# Result: Mobile Community Discovery

- Date: 2026-07-12
- Plan: `docs/work/plans/2026-07-12-mobile-community-discovery.md`
- Status: Complete

## Outcome

The persistent five-item mobile navigation now exposes **Спільнота** directly instead of **Новини**. News remains consistently available from the mobile sections menu, the community remains there as a secondary route, and desktop navigation is unchanged.

## Verification

- At a 320px viewport, the direct community control rendered at 64×60px with no horizontal overflow.
- The shortcut resolved to `/community/sso/start/` and the desktop community link remained visible.
- `djlint --profile=django --lint templates/footer.html`: passed.
- `git diff --check` for the changed files: passed.
- `just test-target core.posts.tests.test_views.ErrorsHandlerTests`: passed (1 test; existing system warnings remain).
