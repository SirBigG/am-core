# Dependencies

Main app dependencies are managed with uv.

Main app:

- `pyproject.toml` is the human-edited dependency input.
- `uv.lock` is the locked transitive dependency set.
- `Dockerfile` installs the locked environment with `uv sync --frozen --all-groups --no-install-project --inexact`.
- `Makefile` uses uv for the `update` target.

The Docker image syncs dependencies into `/usr/local` with `UV_PROJECT_ENVIRONMENT=/usr/local`.
This avoids putting the runtime environment under `/am-core/.venv`, because Docker Compose bind
mounts the source tree into `/am-core` during local development.

Useful commands:

```bash
uv lock
uv sync --frozen --all-groups
docker compose build core
docker compose exec core make test
docker compose exec core python -m pip check
```

When changing direct requirements:

1. Edit dependencies in `pyproject.toml`.
2. Run `uv lock`.
3. Rebuild the service image through the parent Docker Compose stack.
4. Run `pip check`, tests, and the direct dependency audit.

For direct dependency audits, export the lock to a temporary requirements file and run `pip-audit`
against that export. Do not reintroduce checked-in main-app `requirements.in`, `requirements.txt`,
or `constraints.txt` files unless the dependency workflow intentionally changes again.

The forum project now lives outside this repo at `../forum_instance/`. Keep its dependency workflow
with that sibling project instead of reintroducing forum requirements into `am-core`.
