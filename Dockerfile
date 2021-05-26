FROM python:3.9.5-slim

ENV PYTHONUNBUFFERED 1

ENV PROJECT_DIR /am-core

ADD requirements.txt $PROJECT_DIR/

WORKDIR $PROJECT_DIR

RUN apt-get update && \
    apt-get install -y gcc build-essential libpq-dev libjpeg-dev python3-dev && \
    apt-get clean && \
    pip install -r requirements.txt

ADD . /am-core/
