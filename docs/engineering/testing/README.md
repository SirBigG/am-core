# Testing

Baseline verified on 2026-05-12 using the parent Docker Compose stack in `/Users/andriihots/Projects/am-dev`.

## Commands

Run from the parent `am-dev` folder:

```bash
docker compose exec core make test
docker compose exec forum_instance python manage.py test
```

`make test` inside the `core` container runs:

1. `make test_core`
2. `make test_api`
3. `make flake`

Do not run `test_core` and `test_api` in parallel unless the test database names are separated. Both use the same PostgreSQL test database name and will collide during database creation.

## Current Baseline

As of 2026-05-12:

- Core Django tests: 202 passing.
- API tests: 24 passing.
- Flake8: passing.
- Forum tests: 9 passing.

Known warnings that remain useful upgrade signals:

- `django-ckeditor` warns that bundled CKEditor 4 has unfixed security issues.
- `pro_auth.User.email` is the `USERNAME_FIELD` but is not unique.
- Several tests emit timezone warnings for naive datetimes.
- Some list views emit unordered pagination warnings.

## Notes

`settings/test_settings.py` must define static and media URL settings so template tests can render through `django.contrib.staticfiles`.

The forum `manage.py` file is not executable in the container mount, so use `python manage.py test`.
