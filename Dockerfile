FROM python:3.12.13-slim

ENV PYTHONUNBUFFERED=1

ENV PROJECT_DIR=/am-core
ARG GECKODRIVER_VERSION=0.36.0

ADD requirements.txt constraints.txt $PROJECT_DIR/

WORKDIR $PROJECT_DIR

# Install Firefox and wget
RUN apt-get update && apt-get install -y firefox-esr wget

# Download and install geckodriver
RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) geckodriver_arch="linux64" ;; \
        arm64) geckodriver_arch="linux-aarch64" ;; \
        *) echo "Unsupported architecture: $arch"; exit 1 ;; \
    esac; \
    wget -O /tmp/geckodriver.tar.gz "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-${geckodriver_arch}.tar.gz" \
    && tar -xvzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm /tmp/geckodriver.tar.gz

RUN apt-get update && \
    apt-get install -y gcc build-essential libpq-dev libjpeg-dev python3-dev gettext  && \
    apt-get clean && \
    pip install -r requirements.txt -c constraints.txt

ADD . .

CMD ["daphne", "-b 0.0.0.0 -p 8081 -v 0", "settings.asgi:application"]
