# Plan: Knowledge Base Foundation

- Date: 2026-06-21
- Status: Implemented
- Owner: Project team
- Related domain: All domains
- Related decisions: `docs/engineering/decisions/2026-06-21-knowledge-base-and-planning.md`

## Goal

Create the first durable project knowledge-base structure for people and coding agents, with enough process to make future work more predictable.

## Non-Goals

This plan does not fully document every business domain. It only creates the structure and first draft map.

This plan does not redesign the code architecture or enforce DDD boundaries in code.

## Current Understanding

The repository already has useful technical documentation, especially around dependency upgrades and testing, but lacks durable business/domain documentation and a standard planning workflow.

The current Django app layout suggests several candidate business domains, but those candidates still need validation through product knowledge and implementation work.

## Assumptions

Future work will be easier if agents and developers start from shared docs before changing code.

The project should introduce domain-driven design gradually, beginning with language, workflows, rules, and open questions before forcing code-level bounded contexts.

## Proposed Approach

Add:

- A top-level documentation workflow in `docs/README.md`.
- Business domain documentation guidance in `docs/business/`.
- An initial domain map in `docs/business/domains/`.
- Decision record guidance and a first accepted decision in `docs/engineering/decisions/`.
- Planning workflow and a reusable implementation plan template in `docs/work/plans/`.
- Agent instructions in `AGENTS.md` requiring planning for meaningful changes.

## Risks And Unknowns

The initial domain map may mirror current Django apps too closely. It should be treated as a draft, not a final DDD model.

If plans become too large, people and agents may avoid them. Keep plans concise.

## Test Strategy

No runtime tests are required because this is documentation-only work.

Verify by reviewing the docs tree and checking that references between docs and `AGENTS.md` are consistent.

## Documentation Updates

This plan creates the documentation updates directly.

## Implementation Checklist

- [x] Confirm scope and assumptions.
- [x] Add knowledge-base structure.
- [x] Add decision and planning templates.
- [x] Add initial domain map.
- [x] Update `AGENTS.md`.
- [x] Review changed docs for consistency.
