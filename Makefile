MANAGE=manage.py
SETTINGS=agro_portal.settings

deploy: migrate collectstatic compilemessages

update:
	pip install -r requirements.txt
	./node_modules/.bin/webpack --config webpack.config.js

test:
	PYTHONPATH=`pwd` DJANGO_SETTINGS_MODULE=$(SETTINGS) ./$(MANAGE) test
	flake8 --exclude '*migrations*' appl
	flake8 --exclude '*migrations*' utils

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