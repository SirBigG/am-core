# Decision Records

Use this folder for decisions that future contributors should be able to understand without reconstructing the whole chat or pull request.

## When To Write A Decision Record

Create a decision record when work changes or establishes:

- Architecture or module boundaries.
- Domain modeling approach.
- Dependency, framework, or service choices.
- Security, privacy, or data handling policy.
- Long-lived workflow or planning process.
- A trade-off that is likely to be questioned later.

Small implementation choices can stay in the implementation plan or pull request.

## File Naming

Use:

```text
YYYY-MM-DD-short-topic.md
```

Example:

```text
2026-06-21-knowledge-base-and-planning.md
```

## Status Values

- `Proposed` - under discussion or being trialed.
- `Accepted` - current project direction.
- `Superseded` - replaced by a newer decision.
- `Rejected` - considered but not chosen.

Use `template.md` for new records.
