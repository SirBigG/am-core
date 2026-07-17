# Historical Plans

This folder contains plans committed before the repository adopted a local,
gitignored planning workspace. Do not add new plans here.

Planning is required when a change affects product behavior, domain rules, architecture, dependencies, data, security, or a workflow spanning multiple apps or services.

Planning is optional for small mechanical changes such as typos, formatting, local comments, or tiny test corrections.

## Planning Workflow

1. Read the relevant domain note in `docs/business/domains/`.
2. Read relevant decision records in `docs/engineering/decisions/`.
3. Create a dated local plan under `var/agents-work/plans/`.
4. Confirm scope, assumptions, risks, and test strategy before implementation.
5. Update the plan if implementation changes direction.
6. Update domain notes or decision records when new knowledge should persist.

## Local File Naming

Use:

```text
YYYY-MM-DD-short-topic.md
```

Example:

```text
2026-06-21-company-profile-cleanup.md
```

## Plan Size

Prefer concise plans. A good plan can be one or two pages. The point is shared understanding, not paperwork.

At completion or abandonment, promote lasting knowledge to durable docs or
decisions, summarize execution and verification in the pull request, and delete
the local plan.
