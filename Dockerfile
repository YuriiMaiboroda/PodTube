# syntax=docker/dockerfile:1

FROM python:3.10

LABEL net.ftawesome.home.version='2023.08.23.3'

WORKDIR /opt/

ADD ./ /opt/
RUN apt update
RUN apt install -y nano
RUN pip install misaka psutil requests feedgen tornado urllib3 pytz bs4
RUN pip install git+https://github.com/YuriiMaiboroda/pytube@fixes

CMD python /opt/podtube.py
