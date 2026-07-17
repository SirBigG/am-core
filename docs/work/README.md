# Work Artifacts

This folder preserves planning and result artifacts created before new plans
moved to a local gitignored workspace.

Do not add new plans here. Create unfinished plans under
`var/agents-work/plans/`, summarize implementation and verification in the pull
request, and keep durable business knowledge, engineering decisions,
architecture notes, and domain references in `docs/business/` and
`docs/engineering/`.

## Structure

- `plans/` - historical implementation plans from the previous tracked workflow.
- `results/` - historical implementation results and investigation outputs from the previous tracked workflow.

## Working Rule

Historical plans and results may be referenced from durable docs, but they are
not current-state authority and must not replace durable docs.

When a work artifact discovers lasting knowledge, update the relevant domain note, decision record, dependency note, security note, or testing note.

See `docs/engineering/decisions/2026-07-17-local-agent-plans.md` for the current
workflow and lifecycle.
