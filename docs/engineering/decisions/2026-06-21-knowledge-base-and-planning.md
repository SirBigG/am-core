# Decision: Knowledge Base And Planning Workflow

- Date: 2026-06-21
- Status: Accepted
- Owners: Project team

## Context

The project has useful dependency and upgrade history, but it does not yet have enough durable business, domain, and planning documentation. That makes agent work and human implementation less predictable: important context stays in chats, assumptions are rediscovered repeatedly, and implementation can start before scope and risk are clear.

The project also needs a lightweight way to introduce domain-driven design practices without blocking everyday delivery.

## Decision

`docs/` is the shared knowledge base for people and agents.

The knowledge base is organized around:

- Business domain notes in `docs/business/domains/`.
- Engineering decision records in `docs/engineering/decisions/`.
- Implementation plans in `docs/work/plans/`.
- Result artifacts in `docs/work/results/`.
- Existing technical topic folders such as `dependencies/`, `package-upgrades/`, and `testing/`.

Meaningful implementation work should begin with a short plan when it affects product behavior, domain rules, architecture, dependencies, data, security, or cross-app workflows. The plan should use `docs/work/plans/template.md` unless the work already has an equivalent planning artifact.

Work result artifacts should be written under `docs/work/results/` when implementation needs a durable summary of what happened, what was verified, and what follow-up remains.

Domain notes should be updated as work reveals business language, rules, workflows, states, integrations, or open questions.

## Consequences

This gives agents and developers a predictable starting point before changing code.

It creates a durable place for business understanding, not only technical upgrade history.

It adds a small documentation cost to meaningful work, but that cost should reduce rework, unclear scope, and accidental architecture drift.

## Alternatives Considered

Only using `AGENTS.md` was rejected because the agent file becomes too large and too operational. It should point to the knowledge base, not contain the whole knowledge base.

Only writing plans in chat was rejected because chat context is not durable enough for future contributors.

Introducing a heavy DDD process immediately was rejected. The project will start with domain notes, ubiquitous language, bounded-context candidates, and explicit open questions, then refine as real work happens.

## Follow-Up

- Fill `docs/business/domains/` domain notes as product areas are touched.
- Add decision records for major architecture and domain modeling choices.
- Keep implementation plans close to the work and update them when scope changes.
