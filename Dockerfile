FROM nvcr.io/nvidia/pytorch:22.11-py3

ARG DEBIAN_FRONTEND=noninteractive

# Basic DEV tools
RUN apt-get update && \
    apt-get install -y sudo curl git-core gnupg \
    vim locales zsh wget nano \
    xorg-dev libx11-dev libgl1-mesa-glx \
    python3-tk \
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

RUN mkdir -m 0755 -p /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

RUN sudo apt-get update && apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

RUN groupadd -f docker
RUN usermod -aG docker devuser
RUN newgrp docker

USER devuser

ENV TORCH=1.13.0
ENV CUDA='cu117'

RUN mkdir /home/devuser/dev /home/devuser/app
COPY --chown=devuser . /home/devuser/app
WORKDIR /home/devuser/app
RUN pip install -e .

RUN pip install pyg-lib \
    torch-scatter \
    torch-sparse -f https://data.pyg.org/whl/torch-${TORCH}+${CUDA}.html
