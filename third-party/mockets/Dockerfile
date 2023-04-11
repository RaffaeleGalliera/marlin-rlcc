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
    ca-certificates \
    curl \
    gnupg \
    fonts-powerline && \
    locale-gen en_US.UTF-8 && \
    adduser --quiet --disabled-password \
    --shell /bin/zsh --home /home/devuser \
    --gecos "User" devuser && \
    echo "devuser:<a href="mailto://p@ssword1">p@ssword1</a>" | \
    chpasswd &&  usermod -aG sudo devuser

USER devuser

RUN mkdir /home/devuser/dev /home/devuser/app
COPY --chown=devuser . /home/devuser/app
WORKDIR /home/devuser/app/
RUN unzip -a driver.zip

WORKDIR /home/devuser/app/driver
