FROM python:3.6.4-alpine

RUN apk --no-cache add autoconf automake postgresql-dev gcc python3-dev musl-dev

ENV PYTHONUNBUFFERED 1

RUN mkdir /am-core

WORKDIR /am-core

RUN apk --no-cache add g++ libxml2-dev libxslt-dev jpeg-dev zlib-dev freetype-dev lcms2-dev \
   openjpeg-dev tiff-dev tk-dev tcl-dev

RUN apk --no-cache add build-base linux-headers pcre-dev

RUN apk --no-cache add git

ADD requirements.txt /am-core/

RUN pip install -r requirements.txt && pip3 install uwsgi && mkdir /am-core/tmp && \
   mkdir /am-core/docker && touch /am-core/tmp/uwsgi.log
ADD docker/uwsgi.ini /am-core/docker/

ADD . /am-core/

RUN python manage.py collectstatic --noinput --settings=settings.dev
