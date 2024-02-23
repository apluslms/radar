FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt update -y
RUN apt install -y python3 python3-pip git gettext curl firefox
RUN pip3 install --upgrade pip setuptools wheel

# install python requirements
COPY requirements.txt requirements.txt
RUN pip install prospector
RUN pip install -r requirements.txt

ENV APLUS_BASE_URL="-"
