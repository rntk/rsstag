FROM node:14-alpine as JSBundle

COPY ./ /rsstag

WORKDIR /rsstag/static/js

RUN npm install \
    && NODE_ENV=production ./node_modules/.bin/webpack


FROM ubuntu:20.04

RUN apt-get update \
    && apt-get -y install python3-pip curl

COPY --from=JSBundle /rsstag /rsstag

WORKDIR /rsstag

RUN curl https://storage.yandexcloud.net/natasha-slovnet/packs/slovnet_ner_news_v1.tar -o ./data/slovnet_ner_news_v1.tar \
    && curl https://storage.yandexcloud.net/natasha-navec/packs/navec_news_v1_1B_250K_300d_100q.tar -o ./data/navec_news_v1_1B_250K_300d_100q.tar \
    && pip3 install -r requirements.txt

EXPOSE 8885
CMD python3 worker.py & python3 web.py

