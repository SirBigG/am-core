FROM python:3.12.2-slim

ENV PYTHONUNBUFFERED=1

ENV PROJECT_DIR=/am-core

ADD requirements.txt $PROJECT_DIR/

WORKDIR $PROJECT_DIR

# Install Firefox and wget
RUN apt-get update && apt-get install -y firefox-esr wget

# Download and install geckodriver
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.30.0/geckodriver-v0.30.0-linux64.tar.gz \
    && tar -xvzf geckodriver-v0.30.0-linux64.tar.gz \
    && mv geckodriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm geckodriver-v0.30.0-linux64.tar.gz

RUN apt-get update && \
    apt-get install -y gcc build-essential libpq-dev libjpeg-dev python3-dev gettext  && \
    apt-get clean && \
    pip install -r requirements.txt

ADD . .

CMD ["daphne", "-b 0.0.0.0 -p 8081 -v 0", "settings.asgi:application"]
