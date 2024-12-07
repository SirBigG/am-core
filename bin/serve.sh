#!/bin/sh

# /bin/sh -c "python manage.py collectstatic --noinput --settings=$DJANGO_SETTINGS_MODULE"
/bin/sh -c "python manage.py migrate --settings=$DJANGO_SETTINGS_MODULE"
/bin/sh -c "python manage.py runserver 0.0.0.0:8081 --settings=$DJANGO_SETTINGS_MODULE"
