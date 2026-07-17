# Decision: Keep Agent Plans In A Local Gitignored Workspace

- Date: 2026-07-17
- Status: Accepted
- Owners: Project team
- Supersedes: `2026-06-21-knowledge-base-and-planning.md` for plan and result artifact storage

## Context

Tracked implementation plans preserve temporary intent after a task ends. They
create review noise, appear in broad documentation searches, and can compete
with code, tests, durable documentation, and newer decisions as descriptions of
current behavior. Developers still benefit from keeping an inspectable plan
beside the code while work is active.

## Decision

- Store every new unfinished plan under gitignored
  `var/agents-work/plans/`.
- Treat local plans and supporting analysis as non-authoritative task workspace.
- Keep shared requirements and acceptance criteria in the owning task tracker.
- Put implementation summaries, verification, risks, and follow-ups in the pull
  request by default.
- Promote lasting current behavior into business or engineering documentation
  and material rationale into decision records.
- Delete local plans and their supporting analysis when work completes or is
  abandoned.
- Retain existing `docs/work/` files as historical records, but do not add new
  plans there or treat them as current-state authority.

## Consequences

- A clean clone contains no active plans, and CI cannot depend on them.
- Plans remain visible beside the code in a developer's local editor.
- Local plans do not transfer automatically between machines or contributors.
- Handoffs require the task tracker, pull request, or deliberate out-of-band
  sharing.
- Durable knowledge must be promoted explicitly before a plan is deleted.

## Alternatives Considered

- Continuing to commit plans was rejected because temporary intent becomes
  permanent repository content and review history.
- Keeping plans outside the repository was rejected because local plans are more
  useful when visible beside the code.
- Deleting all historical plans in this change was rejected because the goal is
  to prevent future tracked plans without silently removing existing project
  records.
