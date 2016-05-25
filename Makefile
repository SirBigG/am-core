MANAGE=manage.py
SETTINGS=agro_portal.settings

deploy: update webpack test migrate collectstatic compilemessages

update:
	pip install -r requirements.txt
	npm install

test:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) test
	flake8 --exclude '*migrations*' appl utils

migrate:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) migrate

collectstatic:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) collectstatic

makemessages:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) makemessages -l uk --ignore=env/*

compilemessages:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) compilemessages -l uk

runserver:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) runserver

webpack:
	webpack

dev:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) runserver --settings=agro_portal.dev

coverage:
	coverage run manage.py test
	coverage report -m --include=appl/*,utils/*

reload:
	uwsgi --reload /home/agr/golub_portal/agro_portal/tmp/project-master.pid