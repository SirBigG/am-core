# Business Domains

This folder captures the business areas represented by `am-core`. It is the starting point for introducing domain-driven design practices into the project.

The current notes are intentionally lightweight. They should become more precise as people and agents work on each area.

## How To Use Domain Notes

Before implementing a feature or bug fix, check the relevant domain note. If the note is missing or incomplete, add the facts and open questions discovered during the work.

Prefer business terms. Mention code modules only when they help readers connect the domain to the implementation.

## Candidate Domains

The current Django app layout suggests these initial domain candidates:

- Advertising marketplace - `core/adverts`; see `advertising-marketplace/`.
- Analytics and metrics - `core/analytics`.
- Classification and taxonomy - `core/classifier`; see `classification-and-taxonomy/`.
- Companies and shops - `core/companies`; see `companies-and-shops/`.
- Diary and journals - `core/diary`; see `diary-and-journals/`.
- Events calendar - `core/events`; see `events-calendar/`.
- News and editorial content - `core/news`.
- Catalog information - `core/posts`; see `catalog-information/`.
- Authentication and identity - `core/pro_auth`.
- Registries and reference data - `core/registry`.
- Services and reviews - `core/services`.

These are candidates, not final bounded contexts. As the project moves toward DDD, we should validate whether these areas share language, rules, data ownership, and workflows.

## Domain Note Template

Each current domain should have its own folder with a `README.md` overview. Add supporting notes, investigations, workflow documents, diagrams, or glossary files inside the same folder.

Use this structure for a domain folder `README.md`:

```md
# Domain: Name

## Purpose

## Actors

## Core Workflows

## Business Rules

## States And Lifecycle

## Neighboring Domains

## Implementation Map

## Open Questions
```
