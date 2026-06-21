set shell := ["bash", "-eu", "-o", "pipefail", "-c"]

repo_dir := justfile_directory()
compose_dir := repo_dir + "/.."
compose := "docker compose --project-directory " + compose_dir
core := compose + " exec core"
forum := compose + " exec forum_instance"
manage := core + " ./manage.py"
settings := "settings.settings"
dev_settings := "settings.dev"
test_settings := "settings.test_settings"
core_image := "sirbigg/am-core:latest"
docker_platform := "linux/x86_64"

# Show available commands.
default:
    @just --list

# Start the local Docker Compose stack in the background.
start:
    {{compose}} up -d

# Start the local Docker Compose stack in the foreground.
up:
    {{compose}} up

# Stop containers without removing them.
stop:
    {{compose}} stop

# Stop and remove containers, networks, and default resources.
down:
    {{compose}} down

# Restart the core app container.
restart:
    {{compose}} restart core

# Show Docker Compose service status.
ps:
    {{compose}} ps

# Build the core Docker image.
build:
    {{compose}} build core

# Build both app Docker images.
build-all:
    {{compose}} build core forum_instance

# Follow logs for a service, defaulting to core.
logs service="core":
    {{compose}} logs -f {{service}}

# Run an arbitrary command inside the core container, for example: just exec python --version
exec *args:
    {{core}} {{args}}

# Open a shell inside the core container.
shell:
    {{core}} bash

# Run an arbitrary Django manage.py command inside core, for example: just manage createsuperuser
manage *args:
    {{manage}} {{args}}

# Run Django migrations inside core.
migrate *args:
    {{manage}} migrate {{args}} --settings={{settings}}

# Create Django migrations inside core.
makemigrations *args:
    {{manage}} makemigrations {{args}} --settings={{settings}}

# Collect static files inside core with local Docker settings.
collectstatic:
    {{manage}} collectstatic --noinput -i node_modules --settings={{dev_settings}}

# Create Ukrainian translation messages inside core.
messages:
    {{manage}} makemessages -l uk --ignore=env/* --settings={{settings}}

# Compile Ukrainian translation messages inside core.
compilemessages:
    {{manage}} compilemessages -l uk --settings={{settings}}

# Run Django's system check with test settings.
check:
    {{manage}} check --settings={{test_settings}}

# Run all core checks: Django tests, API tests, and flake8.
test: test-core test-api flake

# Run Django tests inside core. Pass a dotted target with: just test-target core.adverts
test-core:
    {{manage}} test --settings={{test_settings}}

# Run tests for a specific target inside core.
test-target target:
    {{manage}} test {{target}} --settings={{test_settings}}

# Run API tests inside core.
test-api:
    {{manage}} test api --settings={{test_settings}}

# Run flake8 inside core.
flake:
    {{core}} flake8

# Run template lint for the whole project inside core.
lint-templates:
    {{core}} uv tool run djlint --profile=django --lint .

# Check that uv.lock and the installed frozen environment are current.
check-deps:
    {{core}} uv lock --check
    {{core}} uv sync --frozen --all-groups --no-install-project --inexact --check

# Sync the locked dependency environment inside core.
update:
    {{core}} env UV_PROJECT_ENVIRONMENT=/usr/local uv sync --frozen --all-groups --no-install-project --inexact

# Run pip check inside core.
pip-check:
    {{core}} python -m pip check

# Run the local forum test suite.
forum-test:
    {{forum}} python manage.py test

# Open a Django shell with production settings.
django-shell:
    {{manage}} shell --settings={{settings}}

# Open a Django shell with dev settings.
dev-shell:
    {{manage}} shell --settings={{dev_settings}}

# Run the development server inside core.
runserver:
    {{manage}} runserver 0.0.0.0:8000 --settings={{settings}}

# Run the development server with dev settings inside core.
dev:
    {{manage}} runserver 0.0.0.0:8000 --settings={{dev_settings}}

# Run the old deployment sequence with the new just commands.
deploy: update test migrate collectstatic compilemessages

# Build and push the release image.
release: release-build release-push

# Build the release image.
release-build:
    docker build --platform {{docker_platform}} -t {{core_image}} .

# Push the release image.
release-push:
    docker push {{core_image}}
