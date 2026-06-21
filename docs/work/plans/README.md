# Plans

Use this folder for implementation plans that should outlive a chat.

Planning is required when a change affects product behavior, domain rules, architecture, dependencies, data, security, or a workflow spanning multiple apps or services.

Planning is optional for small mechanical changes such as typos, formatting, local comments, or tiny test corrections.

## Planning Workflow

1. Read the relevant domain note in `docs/business/domains/`.
2. Read relevant decision records in `docs/engineering/decisions/`.
3. Create a dated plan in this folder from `template.md`.
4. Confirm scope, assumptions, risks, and test strategy before implementation.
5. Update the plan if implementation changes direction.
6. Update domain notes or decision records when new knowledge should persist.

## File Naming

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

## Results

After implementation, write result artifacts in `docs/work/results/` when the work needs a durable execution summary, verification record, audit output, or follow-up list.
