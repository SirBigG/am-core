MANAGE=manage.py
SETTINGS=agro_portal.settings
DEV_SETTINGS=agro_portal.dev

deploy: pull update webpack test migrate statics compilemessages

update:
	pip install -r requirements.txt
	cd assets && npm install --no-optional

test:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) test
	flake8 --exclude '*migrations*' appl

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
	cd assets && webpack

dev:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(DEV_SETTINGS) ./$(MANAGE) runserver

coverage:
	coverage run manage.py test
	coverage report -m --include=appl/*

pull:
	git pull origin master

reload:
	uwsgi --reload /home/agr/golub_portal/agro_portal/tmp/project-master.pid