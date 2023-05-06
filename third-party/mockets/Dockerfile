FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive

# Basic DEV tools
RUN apt-get update && \
    apt-get install -y sudo curl git-core gnupg \
    vim locales zsh wget nano \
    xorg-dev libx11-dev libgl1-mesa-glx \
    openjdk-11-jdk \
    zip \
    net-tools \
    iputils-ping \
    iproute2 \
    ca-certificates \
    curl

RUN mkdir /home/dev /home/app
COPY . /home/app
WORKDIR /home/app/

CMD /bin/bash

