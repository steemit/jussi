# -*- coding: utf-8 -*-
import functools
import itertools as it
import json
import logging
import os
import re
import socket
from typing import NamedTuple
from urllib.parse import urlparse

import jsonschema
import pygtrie

import ujson

from .errors import InvalidUpstreamHost
from .errors import InvalidUpstreamURL

logger = logging.getLogger(__name__)

ACCOUNT_TRANSFER_PATTERN = re.compile(r'^\/?@([^\/\s]+)/transfers$')


#-------------------
# TTLS
# NO EXPIRE: 0
# NO CACHE: -1
# NO EXPIRE IF IRREVERSIBLE: -2
#-------------------
#  TIMEOUTS
#  NO TIMEOUT: 0
#-------------------
#  RETRIES
#  NO RETRIES: 0
#-------------------


UPSTREAM_SCHEMA_FILE = 'upstreams_schema.json'
with open(UPSTREAM_SCHEMA_FILE) as f:
    UPSTREAM_SCHEMA = json.load(f)
jsonschema.Draft4Validator.check_schema(UPSTREAM_SCHEMA)
CONFIG_VALIDATOR = jsonschema.Draft4Validator(UPSTREAM_SCHEMA)


class _Upstreams(object):
    __NAMESPACES = None
    __URLS = None
    __TTLS = None
    __TIMEOUTS = None

    def __init__(self, config, validate=True):
        CONFIG_VALIDATOR.validate(config)
        self.config = config
        self.__hash = hash(ujson.dumps(config))
        self.__translate_to_appbase = False

        for upstream in config:
            if upstream['name'] == 'steemd':
                self.__translate_to_appbase = upstream.get('translate_to_appbase', False)

        self.__NAMESPACES = frozenset(c['name'] for c in self.config)
        for namespace in self.__NAMESPACES:
            assert not namespace.endswith('_api'),\
                f'Invalid namespace {namespace} : Namespaces cannot end with "_api"'
            assert not namespace == 'jsonrpc',\
                f'Invalid namespace {namespace} : Namespace "jsonrpc" is not allowed'

        self.__URLS = pygtrie.StringTrie(
            it.chain.from_iterable(c['urls'] for c in self.config),
            separator='.')

        self.__TTLS = pygtrie.StringTrie(
            it.chain.from_iterable(c['ttls'] for c in self.config),
            separator='.')

        self.__TIMEOUTS = pygtrie.StringTrie(
            it.chain.from_iterable(c['timeouts'] for c in self.config),
            separator='.')

        if validate:
            self.validate_urls()

    @functools.lru_cache(8192)
    def url(self, request_urn) -> str:
        try:
            if request_urn.api == 'database_api' and ACCOUNT_TRANSFER_PATTERN.match(
                    request_urn.params[0]):
                logger.debug('matched')
                url = os.environ.get('JUSSI_ACCOUNT_TRANSFER_STEEMD_URL')
                if url:
                    return url
        except Exception:
            pass
        _, url = self.__URLS.longest_prefix(str(request_urn))
        if not url:
            raise InvalidUpstreamURL(
                url=url, reason='No matching url found', data={
                    'urn': str(request_urn)})
        elif url.startswith('ws') or url.startswith('http'):
            return url
        raise InvalidUpstreamURL(url=url, reason='invalid format', data={'urn': str(request_urn)})

    @functools.lru_cache(8192)
    def ttl(self, request_urn: NamedTuple) -> str:
        _, ttl = self.__TTLS.longest_prefix(str(request_urn))
        return ttl

    @functools.lru_cache(8192)
    def timeout(self, request_urn: NamedTuple) -> int:
        _, timeout = self.__TIMEOUTS.longest_prefix(str(request_urn))
        if timeout is 0:
            timeout = None
        return timeout

    def urls(self) -> frozenset:
        return frozenset(u for u in self.__URLS.values())

    @property
    def namespaces(self)-> frozenset:
        return self.__NAMESPACES

    @property
    def translate_to_appbase(self):
        return self.__translate_to_appbase

    def validate_urls(self):
        logger.info('testing upstream urls')
        for url in self.urls():
            try:
                parsed_url = urlparse(url)
                host = urlparse(url).netloc
                logger.info('attempting to add %s', parsed_url)
                socket.gethostbyname(host)
                logger.info('added %s', parsed_url)
            except socket.gaierror:
                raise InvalidUpstreamHost(url=url)
            except Exception as e:
                raise InvalidUpstreamURL(url=url, reason=str(e))

    def __hash__(self):
        return self.__hash


class Upstream(NamedTuple):
    url: str
    ttl: int
    timeout: int

    @classmethod
    @functools.lru_cache(4096)
    def from_urn(cls, urn: NamedTuple, upstreams: _Upstreams=None):
        return cls(upstreams.url(urn),
                   upstreams.ttl(urn),
                   upstreams.timeout(urn))
