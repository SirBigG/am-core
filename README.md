# AgroMega Core

AgroMega Django backend and API project. The forum instance is kept in
`forum_instance/` and runs as a separate Django project.

## Local Development

The project is normally run from the parent `am-dev` folder with Docker Compose.

Compose file:

```text
/Users/andriihots/Projects/am-dev/docker-compose.yml
```

Common commands from the parent folder:

```bash
docker compose up
docker compose ps
docker compose exec core ./manage.py test --settings=settings.test_settings
docker compose exec core ./manage.py test api --settings=settings.test_settings
docker compose exec core flake8
docker compose exec forum_instance ./manage.py test
```

Nginx exposes the local app on port `8000`. The compose setup mounts this repo
into the `core` container at `/am-core` and mounts `forum_instance/` into the
forum container at `/app`.

## Documentation

Project docs live under `docs/`:

- `docs/engineering/` for technical plans, architecture notes, investigations,
  upgrade reports, and implementation records.
- `docs/business/` for product, domain, operations, content, and other future
  business documentation.

Current package upgrade and test plan:

- `docs/engineering/package-upgrades/2026-05-11-package-upgrade-test-plan.md`

Agent-specific project memory lives in `AGENTS.md`.
