FROM python:3.10-bookworm

WORKDIR /app

RUN apt update && apt install -y git libfreetype6-dev gcc musl-dev libffi-dev g++ curl tar python3

RUN adduser --disabled-password prospector \
    && chown -R prospector:prospector /app \
    && rm -rf ${HOME}/.cache/ ${HOME}/.local/bin/__pycache__/
USER prospector

ENV PATH /home/prospector/.local/bin:${PATH}


COPY requirements.txt /app/
RUN pip3 install prospector
RUN pip3 install --compile -r requirements.txt
RUN rm /app/requirements.txt
