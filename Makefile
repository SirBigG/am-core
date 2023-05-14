MANAGE=manage.py
SETTINGS=settings.settings
DEV_SETTINGS=settings.dev
TEST_SETTINGS=settings.test_settings

deploy: pull update test migrate statics compilemessages

update:
	pip install -r requirements.txt

test: test_core test_api flake

test_core:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(TEST_SETTINGS) ./$(MANAGE) test --settings=$(TEST_SETTINGS)

test_api:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(TEST_SETTINGS) ./$(MANAGE) test api --settings=$(TEST_SETTINGS)

flake:
	flake8

migrate:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) migrate

statics:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) collectstatic --noinput -i node_modules

messages:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) makemessages -l uk --ignore=env/*

compilemessages:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) compilemessages -l uk

runserver:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) runserver

dev:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(DEV_SETTINGS) ./$(MANAGE) runserver

coverage: coverage_core coverage_api

coverage_core:
	coverage run manage.py test --settings=$(TEST_SETTINGS)
	coverage report -m --include=core/*

coverage_api:
	coverage run manage.py test api --settings=$(TEST_SETTINGS)
	coverage report -m --include=api/*

pull:
	git pull origin master


release:
	docker build --platform linux/x86_64 -t sirbigg/am-core:latest .
	docker push sirbigg/am-core:latest
