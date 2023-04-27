# syntax=docker/dockerfile:1

FROM python:3.10

LABEL net.ftawesome.home.version='2023.04.26.1'

WORKDIR /opt/

ADD ./ /opt/
RUN pip install misaka psutil requests feedgen pytube tornado urllib3 pytz bs4

CMD python /opt/podtube.py
