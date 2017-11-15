 FROM python:3.6

 ENV PYTHONUNBUFFERED 1

 RUN mkdir /am-core
 WORKDIR /am-core
 ADD requirements.txt /am-core/

 RUN pip3 install -r requirements.txt && pip3 install uwsgi && mkdir /am-core/tmp && mkdir /am-core/docker && touch /am-core/tmp/uwsgi.log
 ADD docker/uwsgi.ini /am-core/docker/

 ADD . /am-core/

 RUN python manage.py collectstatic --noinput --settings=settings.dev


