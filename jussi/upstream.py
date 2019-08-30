# -*- coding: utf-8 -*-
import functools
import itertools as it
import json
import os
import re
import socket
from typing import NamedTuple
from urllib.parse import urlparse

import jsonschema
import pygtrie
import structlog
import ujson

from .errors import InvalidUpstreamHost
from .errors import InvalidUpstreamURL

logger = structlog.get_logger(__name__)

ACCOUNT_TRANSFER_PATTERN = re.compile(r'^\/?(@([^\/\s]+)/transfers|~?witnesses|proposals)$')


# -------------------
# TTLS
# NO EXPIRE: 0
# NO CACHE: -1
# NO EXPIRE IF IRREVERSIBLE: -2
# -------------------
#  TIMEOUTS
#  NO TIMEOUT: 0
# -------------------
#  RETRIES
#  NO RETRIES: 0
# -------------------


UPSTREAM_SCHEMA_FILE = 'upstreams_schema.json'
with open(UPSTREAM_SCHEMA_FILE) as f:
    UPSTREAM_SCHEMA = json.load(f)
jsonschema.Draft4Validator.check_schema(UPSTREAM_SCHEMA)
#CONFIG_VALIDATOR = jsonschema.Draft4Validator(UPSTREAM_SCHEMA)


class _Upstreams(object):
    __NAMESPACES = None
    __URLS = None
    __TTLS = None
    __TIMEOUTS = None
    __TRANSLATE_TO_APPBASE = None

    def __init__(self, config, validate=True):
        upstream_config = config['upstreams']
        # CONFIG_VALIDATOR.validate(upstream_config)
        self.config = upstream_config
        self.__hash = hash(ujson.dumps(self.config))

        self.__NAMESPACES = frozenset(c['name'] for c in self.config)
        for namespace in self.__NAMESPACES:
            assert not namespace.endswith('_api'),\
                f'Invalid namespace {namespace} : Namespaces cannot end with "_api"'
            assert not namespace == 'jsonrpc',\
                f'Invalid namespace {namespace} : Namespace "jsonrpc" is not allowed'

        self.__URLS = self.__build_trie('urls')
        self.__TTLS = self.__build_trie('ttls')
        self.__TIMEOUTS = self.__build_trie('timeouts')

        self.__TRANSLATE_TO_APPBASE = frozenset(
            c['name'] for c in self.config if c.get('translate_to_appbase', False) is True)

        if validate:
            self.validate_urls()

    def __build_trie(self, key):
        trie = pygtrie.StringTrie(separator='.')
        for item in it.chain.from_iterable(c[key] for c in self.config):
            if isinstance(item, list):
                prefix, value = item
            else:
                keys = list(item.keys())
                prefix_key = 'prefix'
                value_key = keys[keys.index(prefix_key) - 1]
                prefix = item[prefix_key]
                value = item[value_key]
            trie[prefix] = value
        return trie

    @functools.lru_cache(8192)
    def url(self, request_urn) -> str:
        # certain steemd.get_state paths must be routed differently
        if (request_urn.api in ['database_api', 'condenser_api']
                and request_urn.method == 'get_state'
                and isinstance(request_urn.params, list)
                and len(request_urn.params) == 1
                and ACCOUNT_TRANSFER_PATTERN.match(request_urn.params[0])):
            url = os.environ.get('JUSSI_ACCOUNT_TRANSFER_STEEMD_URL')
            if url:
                return url

        _, url = self.__URLS.longest_prefix(str(request_urn))
        if not url:
            raise InvalidUpstreamURL(
                url=url, reason='No matching url found', urn=str(request_urn))
        elif url.startswith('ws') or url.startswith('http'):
            return url
        raise InvalidUpstreamURL(url=url, reason='invalid format', urn=str(request_urn))

    @functools.lru_cache(8192)
    def ttl(self, request_urn) -> int:
        _, ttl = self.__TTLS.longest_prefix(str(request_urn))
        return ttl

    @functools.lru_cache(8192)
    def timeout(self, request_urn) -> int:
        _, timeout = self.__TIMEOUTS.longest_prefix(str(request_urn))
        if timeout is 0:
            timeout = None
        return timeout

    @property
    def urls(self) -> frozenset:
        return frozenset(u for u in self.__URLS.values())

    @property
    def namespaces(self)-> frozenset:
        return self.__NAMESPACES

    def translate_to_appbase(self, request_urn) -> bool:
        return request_urn.namespace in self.__TRANSLATE_TO_APPBASE

    def validate_urls(self):
        logger.info('testing upstream urls')
        for url in self.urls:
            try:
                parsed_url = urlparse(url)
                host = urlparse(url).hostname
                logger.info('attempting to add uptream url', url=parsed_url)
                socket.gethostbyname(host)
                logger.info('added upstream url', url=parsed_url)
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
    def from_urn(cls, urn, upstreams: _Upstreams=None):
        return Upstream(upstreams.url(urn),
                        upstreams.ttl(urn),
                        upstreams.timeout(urn))
