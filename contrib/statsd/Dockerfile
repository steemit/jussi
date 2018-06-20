FROM python:3.6-alpine
RUN mkdir /app

RUN apk add --no-cache --virtual .build-deps  \
        bzip2-dev \
        coreutils \
        dpkg-dev dpkg \
        expat-dev \
        gcc \
        gdbm-dev \
        libc-dev \
        libffi-dev \
        libnsl-dev \
        libressl \
        libressl-dev \
        libtirpc-dev \
        linux-headers \
        make \
        ncurses-dev \
        pax-utils \
        readline-dev \
        sqlite-dev \
        tcl-dev \
        tk \
        tk-dev \
        xz-dev \
        zlib-dev
RUN pip install uvloop
RUN apk del .build-deps
COPY udpserver.py /app/udpserver.py
EXPOSE 8125/udp
WORKDIR /app
CMD ["/app/udpserver.py"]
