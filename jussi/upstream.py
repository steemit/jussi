# -*- coding: utf-8 -*-
import http.client
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

from .errors import InvalidUpstreamHost
from .errors import InvalidUpstreamURL

logger = logging.getLogger(__name__)

ACCOUNT_TRANSFER_PATTERN = re.compile(r'^\\?/@(.*)/transfers$')


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


DEFAULT_UPSTREAM_CONFIG = [
    {
        "name": "steemd",
        "urls": [
            ["steemd", "wss://steemd.steemit.com"]
        ],
        "ttls": [
            ["steemd", 3],
            ["steemd.login_api", -1],
            ["steemd.network_broadcast_api", -1],
            ["steemd.follow_api", 10],
            ["steemd.market_history_api", 1],
            ["steemd.database_api", 3],
            ["steemd.database_api.get_block", -2],
            ["steemd.database_api.get_block_header", -2],
            ["steemd.database_api.get_content", 1],
            ["steemd.database_api.get_state", 1],
            ["steemd.database_api.get_state.params=['/trending']", 30],
            ["steemd.database_api.get_state.params=['trending']", 30],
            ["steemd.database_api.get_state.params=['/hot']", 30],
            ["steemd.database_api.get_state.params=['/welcome']", 30],
            ["steemd.database_api.get_state.params=['/promoted']", 30],
            ["steemd.database_api.get_state.params=['/created']", 10],
            ["steemd.database_api.get_dynamic_global_properties", 1]
        ],
        "timeouts": [
            ["steemd", 3],
            ["steemd.network_broadcast_api", 0]
        ],
        "retries": [
            ["steemd", 3],
            ["steemd.network_broadcast_api", 0]
        ]
    },
    {
        "name": "sbds",
        "urls": [
            ["sbds", "https://sbds.steemit.com"]
        ],
        "ttls": [
            ["sbds", 3]
        ],
        "timeouts": [
            ["sbds", 3]
        ],
        "retries": [
            ["sbds", 3]
        ]
    },
    {
        "name": "hivemind",
        "urls": [
            ["hivemind", "https://hivemind.steemit.com"]
        ],
        "ttls": [
            ["hivemind", 3]
        ],
        "timeouts": [
            ["hivemind", 3]
        ],
        "retries": [
            ["hivemind", 3]
        ]
    },
    {
        "name": "yo",
        "urls": [
            ["yo", "https://yo.steemit.com"]
        ],
        "ttls": [
            ["yo", 3]
        ],
        "timeouts": [
            ["yo", 3]
        ],
        "retries": [
            ["yo", 3]
        ]
    }
]

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

        self.__NAMESPACES = frozenset(c['name'] for c in self.config)

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

    def url(self, request_urn: NamedTuple) -> str:
        try:
            logger.debug(request_urn.parts.params[0])
            if request_urn.parts.api == 'database_api' and ACCOUNT_TRANSFER_PATTERN.match(
                    request_urn.parts.params[0]):
                logger.debug('matched')
                url = os.environ.get('JUSSI_ACCOUNT_TRANSFER_STEEMD_URL')
            if url:
                return url
        except Exception:
            pass
        _, url = self.__URLS.longest_prefix(str(request_urn))

        if url.startswith('ws') or url.startswith('http'):
            return url
        raise InvalidUpstreamURL(url=url, reason='inalid format')

    def ttl(self, request_urn: NamedTuple) -> str:
        _, ttl = self.__TTLS.longest_prefix(str(request_urn))
        return ttl

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

    def validate_urls(self):
        logger.info('testing upstream urls')
        for url in self.urls():
            try:
                parsed_url = urlparse(url)
                host = urlparse(url).netloc
                logger.info('attempting to add %s', parsed_url)
                logger.info('HTTP HEAD / %s', host)
                if parsed_url.scheme.startswith('http'):
                    conn = http.client.HTTPSConnection(host, port=443)
                    conn.request("HEAD", "/")
                    response = conn.getresponse()
                    assert response.status < 500, f'{url} returned HTTP status {response.status}'
                    logger.info('success:  HTTP HEAD / %s', host)
                elif parsed_url.scheme.startswith('ws'):
                    _ = socket.gethostbyname(host)
                else:
                    raise InvalidUpstreamURL(url=url, reason='bad format')

            except socket.gaierror:
                raise InvalidUpstreamHost(url=url)
            except AssertionError as e:
                raise InvalidUpstreamURL(url=url, reason=str(e))
            except Exception as e:
                raise InvalidUpstreamURL(url=url, reason=str(e))


class Upstream(NamedTuple):
    url: str
    ttl: int
    timeout: int

    @classmethod
    def from_urn(cls, urn: NamedTuple, upstreams: _Upstreams=None):
        return cls(upstreams.url(urn),
                   upstreams.ttl(urn),
                   upstreams.timeout(urn))
