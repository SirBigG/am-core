# Dependencies

Dependency files are intentionally split between human-edited top-level inputs and verified transitive constraints.

Main app:

- `requirements.in` is the human-edited top-level input.
- `requirements.txt` is the current install input used by existing tooling.
- `constraints.txt` pins the verified transitive dependency set from the Docker Compose `core` container.

Install commands must use the matching constraints file:

```bash
pip install -r requirements.txt -c constraints.txt
```

The forum project now lives outside this repo at `../forum_instance/`. Keep its
dependency workflow with that sibling project instead of reintroducing forum
requirements into `am-core`.

When changing direct requirements:

1. Edit both the service's `requirements.in` and `requirements.txt`.
2. Rebuild the service image through the parent Docker Compose stack.
3. Refresh the matching `constraints.txt` from the rebuilt container's `pip freeze --all`, excluding packaging tools such as `pip`, `setuptools`, and `wheel`.
4. Run `pip check`, tests, and `pip-audit`.

This is a constraints-based workflow, not a fully hashed lock workflow. A future improvement is to adopt `pip-tools` and generate hash-checked compiled requirements.
