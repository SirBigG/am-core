FROM python:3.8.4-slim

ENV PYTHONUNBUFFERED 1

ENV PROJECT_DIR /am-core

ADD requirements.txt $PROJECT_DIR/

WORKDIR $PROJECT_DIR

RUN apt-get update && \
    apt-get install -y gcc build-essential libpq-dev libjpeg-dev python3-dev && \
    apt-get clean && \
    pip install -r requirements.txt && \
    pip install uwsgi && \
    mkdir /am-core/tmp && \
    mkdir /am-core/docker && touch /am-core/tmp/uwsgi.log

ADD docker/uwsgi.ini /am-core/docker/

ADD . /am-core/
