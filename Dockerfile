FROM phusion/baseimage:0.9.19

ENV LOG_LEVEL INFO
ENV LANG en_US.UTF-8
ENV LC_ALL en_US.UTF-8
ENV PIPENV_VENV_IN_PROJECT 1
ENV APP_ROOT /app
ENV APP_CMD ${APP_ROOT}/jussi/serve.py

# all nginx env vars must also be changed in service/nginx/nginx.conf
ENV NGINX_SERVER_PORT 8080
ENV JUSSI_SERVER_HOST 0.0.0.0
ENV JUSSI_SERVER_PORT 9000
ENV JUSSI_STEEMD_WS_URL wss://steemd.steemitdev.com
ENV JUSSI_SBDS_HTTP_URL https://sbds.steemitdev.com
ENV JUSSI_REDIS_PORT 6379
ENV ENVIRONMENT DEV

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
        python3-dev \
        python3-pip \
        make \
        nginx \
        runit \
        tk-dev \
        wget \
        golang-go


RUN \
    wget https://www.python.org/ftp/python/3.6.2/Python-3.6.2.tar.xz && \
    tar xvf Python-3.6.2.tar.xz && \
    cd Python-3.6.2/ && \
    ./configure && \
    make altinstall

# add statsd server
RUN mkdir /root/go && \
    cd /root/go && \
    export GOPATH=/root/go && \
    go get github.com/raintank/statsdaemon/cmd/statsdaemon && \
    mv /root/go/bin/statsdaemon /usr/local/bin && \
    cd / && \
    rm -rf /root/go


# add scalyr agent
RUN wget -q https://www.scalyr.com/scalyr-repo/stable/latest/scalyr-repo-bootstrap_1.2.1_all.deb && \
    dpkg -r scalyr-repo scalyr-repo-bootstrap  && \
    dpkg -i ./scalyr-repo-bootstrap_1.2.1_all.deb && \
    apt-get update && \
    apt-get install -y \
        scalyr-repo \
        scalyr-agent-2 && \
    rm scalyr-repo-bootstrap_1.2.1_all.deb


# nginx
RUN \
  mkdir -p /var/lib/nginx/body && \
  mkdir -p /var/lib/nginx/scgi && \
  mkdir -p /var/lib/nginx/uwsgi && \
  mkdir -p /var/lib/nginx/fastcgi && \
  mkdir -p /var/lib/nginx/proxy && \
  chown -R www-data:www-data /var/lib/nginx && \
  mkdir -p /var/log/nginx && \
  touch /var/log/nginx/access.log && \
  touch /var/log/nginx/error.log && \
  chown www-data:www-data /var/log/nginx/*.log && \
  touch /var/run/nginx.pid && \
  chown www-data:www-data /var/run/nginx.pid

ADD . /app

RUN \
    mv /app/service/* /etc/service && \
    chmod +x /etc/service/*/run

WORKDIR /app

# This updates the distro-provided pip and gives us pip3.6 binary
RUN python3.6 -m pip install --upgrade pip


WORKDIR ${APP_ROOT}

# Just enough to build dependencies
COPY ./Pipfile ${APP_ROOT}/Pipfile
COPY ./Makefile ${APP_ROOT}/Makefile

# Install those dependencies
RUN cd ${APP_ROOT} && \
    pip3.6 install -r requirements.txt


# Build+install
RUN cd ${APP_ROOT} && \
    pip3.6 install -e .

RUN pip3.6 install sanic

RUN chown -R www-data . && \
    apt-get remove -y \
        build-essential \
        libffi-dev \
        libssl-dev && \
    apt-get autoremove -y && \
    rm -rf \
        /root/.cache \
        /var/lib/apt/lists/* \
        /tmp/* \
        /var/tmp/* \
        /var/cache/* \
        /usr/include \
        /usr/local/include \


EXPOSE ${NGINX_SERVER_PORT}
