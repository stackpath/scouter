FROM python:3.7.3-alpine

RUN apk add --no-cache \
  bash \
  wget \
  tcpdump \
  unzip \
  tar \
  libcurl \
  chromium-chromedriver \
  chromium \
  firefox-esr \
  nginx \
  bind-tools \
  openjdk8-jre-base

ENV PYCURL_SSL_LIBRARY=openssl

WORKDIR /usr/src/scouter

COPY ./requirements.txt .

ARG GECKO_TAG="v0.24.0"
ARG GECKO_PATH="$GECKO_TAG/geckodriver-$GECKO_TAG-linux64.tar.gz"

ARG BUP_TAG="2.0.1"
ARG BUP_PATH="v$BUP_TAG/browserup-proxy-$BUP_TAG.zip"

RUN apk add --no-cache --virtual builddeps build-base curl-dev linux-headers \
    && pip install --no-cache-dir -r requirements.txt \
    && wget -q https://github.com/mozilla/geckodriver/releases/download/$GECKO_PATH \
    && wget -q https://github.com/browserup/browserup-proxy/releases/download/$BUP_PATH \
    && apk del builddeps

COPY . .

RUN chmod +x entrypoint.sh \
  && mv conf/nginx.conf /etc/nginx/nginx.conf \
  && mv conf/circus.conf /etc/circus.conf

ENTRYPOINT ["./entrypoint.sh"]
