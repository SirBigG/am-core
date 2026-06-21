# Documentation

This folder keeps project knowledge that should survive beyond a single task or chat. It is the shared knowledge base for people and coding agents working on `am-core`.

Good documentation here should answer three questions:

- What do we know about the business or domain?
- What have we decided, and why?
- What is the plan before we change the code?

## Structure

- `business/` - product, domain, operations, content, and other business-facing documentation.
- `engineering/` - technical plans, architecture notes, investigations, upgrade reports, security notes, implementation records, and decision records.
- `engineering/decisions/` - architectural and process decision records.
- `engineering/planning/` - planning workflow and reusable implementation plan template.
- `engineering/testing/` - local test commands, baseline status, and known test-suite warnings.

## How To Use This Knowledge Base

Before starting meaningful implementation work:

1. Read `AGENTS.md`.
2. Check `docs/business/README.md` and the relevant domain note in `docs/business/domains/`.
3. Check recent decision records in `docs/engineering/decisions/`.
4. Create or update a plan under `docs/engineering/planning/` when the change affects product behavior, domain rules, architecture, dependencies, data, security, or a cross-app workflow.
5. Update docs in the same change when implementation discovers new business rules, constraints, or decisions.

Small mechanical fixes do not need a full plan. Examples: typo fixes, formatting-only docs edits, small test expectation corrections, or comments that do not change behavior.

## Document Types

- Domain notes describe business language, actors, workflows, rules, and open questions.
- Decision records document a choice that future contributors should not need to re-litigate from scratch.
- Implementation plans define scope, assumptions, risks, test strategy, and rollout before coding.
- Investigation notes capture research, evidence, and possible next steps when the answer is not yet a decision.

Prefer dated documents inside topic folders for investigations and plans, for example:

- `engineering/planning/YYYY-MM-DD-topic.md`
- `engineering/decisions/YYYY-MM-DD-topic.md`
- `engineering/security/YYYY-MM-DD-topic.md`
- `business/domains/YYYY-MM-DD-topic.md`
