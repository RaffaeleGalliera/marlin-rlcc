FROM nvcr.io/nvidia/pytorch:22.11-py3

ARG DEBIAN_FRONTEND=noninteractive

# Basic DEV tools
RUN apt-get update && \
    apt-get install -y sudo curl git-core gnupg \
    vim locales zsh wget nano \
    xorg-dev libx11-dev libgl1-mesa-glx \
    python3-tk \
    fonts-powerline && \
    locale-gen en_US.UTF-8 && \
    adduser --quiet --disabled-password \
    --shell /bin/zsh --home /home/devuser \
    --gecos "User" devuser && \
    echo "devuser:<a href="mailto://p@ssword1">p@ssword1</a>" | \
    chpasswd &&  usermod -aG sudo devuser

USER devuser

ENV TORCH=1.13.0
ENV CUDA='cu117'

RUN mkdir /home/devuser/dev /home/devuser/app
COPY --chown=devuser . /home/devuser/app
WORKDIR /home/devuser/app
RUN pip install -e .
WORKDIR /home/devuser/dev

RUN pip install pyg-lib \
    torch-scatter \
    torch-sparse -f https://data.pyg.org/whl/torch-${TORCH}+${CUDA}.html

