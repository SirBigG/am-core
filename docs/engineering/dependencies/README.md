# Dependencies

Dependency files are intentionally split between human-edited top-level inputs and verified transitive constraints.

Main app:

- `requirements.in` is the human-edited top-level input.
- `requirements.txt` is the current install input used by existing tooling.
- `constraints.txt` pins the verified transitive dependency set from the Docker Compose `core` container.

Forum app:

- `forum_instance/requirements.in` is the human-edited top-level input.
- `forum_instance/requirements.txt` is the current install input used by existing tooling.
- `forum_instance/constraints.txt` pins the verified transitive dependency set from the Docker Compose `forum_instance` container.

Install commands must use the matching constraints file:

```bash
pip install -r requirements.txt -c constraints.txt
pip install -r forum_instance/requirements.txt -c forum_instance/constraints.txt
```

When changing direct requirements:

1. Edit both the service's `requirements.in` and `requirements.txt`.
2. Rebuild the service image through the parent Docker Compose stack.
3. Refresh the matching `constraints.txt` from the rebuilt container's `pip freeze --all`, excluding packaging tools such as `pip`, `setuptools`, and `wheel`.
4. Run `pip check`, tests, and `pip-audit`.

This is a constraints-based workflow, not a fully hashed lock workflow. A future improvement is to adopt `pip-tools` and generate hash-checked compiled requirements.
