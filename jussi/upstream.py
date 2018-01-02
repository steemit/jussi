# -*- coding: utf-8 -*-
import itertools as it
import logging
from typing import NamedTuple

import pygtrie

from .urn import URN

logger = logging.getLogger(__name__)

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

NAMESPACES = frozenset(
    ['hivemind', 'jussi', 'overseer', 'sbds', 'steemd', 'yo'])


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
        "name": "overseer",
        "urls": [
            ["overseer", "https://overseer.steemit.com"]
        ],
        "ttls": [
            ["overseer", 3]
        ],
        "timeouts": [
            ["overseer", 3]
        ],
        "retries": [
            ["overseer", 3]
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


class _Upstreams(object):
    __NAMESPACES = None
    __URLS = None
    __TTLS = None
    __RETRIES = None
    __TIMEOUTS = None

    def __init__(self, config):
        self.config = config

        self.__NAMESPACES = frozenset(c['name'] for c in self.config)

        self.__URLS = pygtrie.StringTrie(
            it.chain.from_iterable(c['urls'] for c in self.config),
            separator='.')

        self.__TTLS = pygtrie.StringTrie(
            it.chain.from_iterable(c['ttls'] for c in self.config),
            separator='.')

        self.__RETRIES = pygtrie.StringTrie(
            it.chain.from_iterable(c['timeouts'] for c in self.config),
            separator='.')

        self.__TIMEOUTS = pygtrie.StringTrie(
            it.chain.from_iterable(c['timeouts'] for c in self.config),
            separator='.')

    def url(self, request_urn: URN) -> str:
        _, url = self.__URLS.longest_prefix(str(request_urn))
        return url

    def ttl(self, request_urn: URN) -> str:
        _, ttl = self.__TTLS.longest_prefix(str(request_urn))
        return ttl

    def timeout(self, request_urn: URN) -> int:
        _, timeout = self.__TIMEOUTS.longest_prefix(str(request_urn))
        return timeout

    def retries(self, request_urn: URN) -> int:
        _, retries = self.__RETRIES.longest_prefix(str(request_urn))
        return retries

    def urls(self) -> frozenset:
        return frozenset(u for u in self.__URLS.values())

    def namespaces(self)-> frozenset:
        return self.__NAMESPACES


class Upstream(NamedTuple):
    url: str
    ttl: int
    timeout: int
    retries: int

    @classmethod
    def from_urn(cls, urn: URN, upstreams: _Upstreams=None):
        upstreams = upstreams or Upstreams
        return cls(upstreams.url(urn),
                   upstreams.ttl(urn),
                   upstreams.timeout(urn),
                   upstreams.retries(urn))


Upstreams = _Upstreams(DEFAULT_UPSTREAM_CONFIG)
