# syntax=docker/dockerfile:1

FROM python:3.10

LABEL net.ftawesome.home.version='2023.08.23.3'

WORKDIR /opt/

EXPOSE 15000:15000

ADD ./ /opt/
RUN apt update
RUN apt install -y nano ffmpeg
RUN pip install -r /opt/requirements.txt

#token for OAuth
COPY ./google/tokens.json /usr/local/lib/python3.10/site-packages/pytube/__cache__/tokens.json

CMD python /opt/podtube.py --config-file /opt/config.ini
