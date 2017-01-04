MANAGE=manage.py
SETTINGS=agro_portal.settings
DEV_SETTINGS=agro_portal.dev
TEST_SETTINGS=agro_portal.test_settings

deploy: pull update webpack test migrate statics compilemessages

update: pip_update npm_update

pip_update:
	pip install -r requirements.txt

npm_update:
	cd assets && npm install --no-optional

test: test_core test_api flake

test_core:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) test --settings=$(TEST_SETTINGS)

test_api:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) test api --settings=$(TEST_SETTINGS)

flake:
	flake8 --exclude '*migrations*' core api

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

webpack:
	cd assets && npm run build

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

reload:
	uwsgi --reload /home/agr/golub_portal/agro_portal/tmp/project-master.pid