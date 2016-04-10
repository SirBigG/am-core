MANAGE=manage.py
SETTINGS=agro_portal.settings

deploy: test update migrate collectstatic compilemessages

update:
	pip install -r requirements.txt

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
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) compilemessages

runserver:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) runserver

nodejs:
	yum install nodejs
	npm install --save-dev react webpack webpack-bundle-tracker babel babel-loader

dev:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) runserver --settings=agro_portal.dev
