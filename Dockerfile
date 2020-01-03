FROM python:3.7.6-alpine

ENV PYTHONUNBUFFERED 1

ENV PROJECT_DIR /am-core

ADD requirements.txt $PROJECT_DIR/

WORKDIR $PROJECT_DIR

RUN apk --no-cache add autoconf \
                       automake \
                       postgresql-dev \
                       gcc \
                       python3-dev \
                       musl-dev \
                       g++ \
                       libxslt-dev \
                       jpeg-dev \
                       zlib-dev \
                       freetype-dev \
                       lcms2-dev \
                       build-base \
                       linux-headers \
                       pcre-dev \
                       git && \
   pip install -r requirements.txt && \
   pip3 install uwsgi && \
   mkdir /am-core/tmp && \
   mkdir /am-core/docker && touch /am-core/tmp/uwsgi.log

ADD docker/uwsgi.ini /am-core/docker/

ADD . /am-core/
