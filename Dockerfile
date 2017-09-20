FROM phusion/baseimage:0.9.19

ENV LOG_LEVEL INFO
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV PIPENV_VENV_IN_PROJECT 1
ENV APP_ROOT /app
ENV APP_CMD jussi.serve

# all nginx env vars must also be changed in service/nginx/nginx.conf
ENV JUSSI_SERVER_HOST 0.0.0.0
ENV JUSSI_SERVER_PORT 9000
ENV JUSSI_STEEMD_WS_URL wss://steemd.steemitdev.com
ENV JUSSI_SBDS_HTTP_URL https://sbds.steemitdev.com
ENV JUSSI_REDIS_PORT 6379
ENV ENVIRONMENT DEV
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT ${SOURCE_COMMIT}

RUN \
    apt-get update && \
    apt-get install -y \
        build-essential \
        checkinstall \
        daemontools \
        git \
        jq \
        libbz2-dev \
        libc6-dev \
        libffi-dev \
        libgdbm-dev \
        libmysqlclient-dev \
        libncursesw5-dev \
        libreadline-gplv2-dev \
        libsqlite3-dev \
        libssl-dev \
        libxml2-dev \
        libxslt-dev \
        make \
        nginx \
        runit \
        tk-dev \
        wget \
        nodejs \
        git


RUN \
    wget https://www.python.org/ftp/python/3.6.2/Python-3.6.2.tar.xz && \
    tar xvf Python-3.6.2.tar.xz && \
    cd Python-3.6.2/ && \
    ./configure && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.6.2.tar.xz Python-3.6.2/


RUN \
    python3.6 -m pip install --upgrade pip && \
    python3.6 -m pip install pipenv

COPY . /app

RUN \
    mv /app/service/* /etc/service && \
    chmod +x /etc/service/*/run

WORKDIR /app

RUN pipenv install --dev

RUN chown -R www-data . && \
    apt-get remove -y \
        build-essential \
        libffi-dev \
        libssl-dev \
        golang-go \
        git \
        make \
        checkinstall && \
    apt-get clean && \
    apt-get autoremove -y && \
    rm -rf \
        /root/.cache \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/* \
        /var/cache/* \
        /usr/include \
        /usr/local/include

RUN pipenv run pytest

EXPOSE ${NGINX_SERVER_PORT}
