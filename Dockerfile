FROM phusion/baseimage:0.10.1

# container settings
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV ENVIRONMENT PROD
ARG SOURCE_COMMIT
ENV SOURCE_COMMIT ${SOURCE_COMMIT}
ARG DOCKER_TAG
ENV DOCKER_TAG ${DOCKER_TAG}

# python app settings
ENV LOG_LEVEL INFO
ENV PIPENV_VENV_IN_PROJECT 1
ENV PIP_DISABLE_PIP_VERSION_CHECK 1
ENV PIP_DEFAULT_TIMEOUT 120
ENV APP_ROOT /app

# jussi settings
ENV APP_CMD jussi.serve
ENV JUSSI_SERVER_HOST 0.0.0.0
ENV JUSSI_SERVER_PORT 9000
ENV JUSSI_MONITOR_PORT 7777

RUN \
    apt-get update && \
    apt-get install -y \
        build-essential \
        checkinstall \
        daemontools \
        git \
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
        runit \
        tk-dev \
        wget && \
    apt-get clean


RUN \
    wget https://www.python.org/ftp/python/3.6.5/Python-3.6.5.tar.xz && \
    tar xvf Python-3.6.5.tar.xz && \
    cd Python-3.6.5/ && \
    ./configure && \
    make altinstall && \
    cd .. && \
    rm -rf Python-3.6.5.tar.xz Python-3.6.5/

RUN \
    python3.6 -m pip install --upgrade pip && \
    python3.6 -m pip install --no-cache-dir --retries 10 --timeout 120 pipenv

COPY . /app

RUN \
    mv /app/service/* /etc/service && \
    chmod +x /etc/service/*/run

WORKDIR /app

RUN pipenv install --dev

RUN pipenv run pip install --no-cache-dir --upgrade "attrs==19.1.0"

RUN chown -R www-data . && \
    apt-get remove -y \
        build-essential \
        libffi-dev \
        libssl-dev \
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

EXPOSE ${JUSSI_SERVER_PORT}
EXPOSE ${JUSSI_MONITOR_PORT}
