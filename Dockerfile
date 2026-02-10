FROM ubuntu:22.04
ENV PIP_BREAK_SYSTEM_PACKAGES=1

RUN apt-get update \
    && apt-get -y install python3-pip curl git

WORKDIR /rsstag

COPY requirements.txt /rsstag/requirements.txt

RUN pip3 install -r requirements.txt

COPY . /rsstag

EXPOSE 8885
CMD python3 worker.py & python3 web.py

