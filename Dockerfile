FROM docker.io/ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DEBIAN_PRIORITY=high \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get -y upgrade && \
    apt-get -y install \
    xvfb \
    xterm \
    xdotool \
    scrot \
    imagemagick \
    sudo \
    mutter \
    x11vnc \
    build-essential \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    curl \
    git \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    net-tools \
    netcat \
    software-properties-common && \
    sudo add-apt-repository ppa:deadsnakes/ppa && \
    sudo add-apt-repository ppa:mozillateam/ppa && \
    sudo apt-get install -y --no-install-recommends \
    firefox-esr \
    x11-apps \
    xpdf \
    tint2 \
    galculator \
    pcmanfm \
    unzip \
    python3 \
    python3.11 \
    python3.11-dev \
    python3.11-venv && \
    apt-get clean

RUN git clone --branch v1.5.0 https://github.com/novnc/noVNC.git /opt/noVNC && \
    git clone --branch v0.12.0 https://github.com/novnc/websockify /opt/noVNC/utils/websockify && \
    ln -s /opt/noVNC/vnc.html /opt/noVNC/index.html

ENV USERNAME=computeruse \
    HOME=/home/computeruse \
    VIRTUAL_ENV=/home/computeruse/.venv

ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN useradd -m -s /bin/bash -d "$HOME" "$USERNAME" && \
    echo "${USERNAME} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER computeruse
WORKDIR /home/computeruse

COPY --chown=computeruse:computeruse requirements.txt ./requirements.txt
RUN python3.11 -m venv "$VIRTUAL_ENV" && \
    python -m pip install --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY --chown=computeruse:computeruse image/ ./
COPY --chown=computeruse:computeruse app ./app
COPY --chown=computeruse:computeruse computer_use_demo ./computer_use_demo

ARG DISPLAY_NUM=1
ARG HEIGHT=768
ARG WIDTH=1024
ENV DISPLAY_NUM=$DISPLAY_NUM \
    HEIGHT=$HEIGHT \
    WIDTH=$WIDTH

EXPOSE 8000 5900 6080

ENTRYPOINT ["./api_entrypoint.sh"]
