# -*- coding: utf-8 -*-
import logging

from aiocache import SimpleMemoryCache
from aiocache.serializers import NullSerializer

import structlog
logger = structlog.get_logger(__name__)

MEMORY_CACHE_MAX_TTL = 180


class SimpleMaxTTLMemoryCache(SimpleMemoryCache):
    def __init__(self, max_ttl=MEMORY_CACHE_MAX_TTL, **kwargs):
        self.max_ttl = max_ttl
        super().__init__(**kwargs)
        self.serializer = NullSerializer()
    # pylint: disable=too-many-arguments

    async def add(self, key, value, ttl=None, dumps_fn=None, namespace=None, _conn=None):
        if ttl is None or ttl > self.max_ttl:
            ttl = self.max_ttl
        return await super().add(key, value, ttl=ttl, dumps_fn=dumps_fn, namespace=namespace, _conn=_conn)

    async def set(self, key, value, ttl=None, dumps_fn=None, namespace=None, _cas_token=None, _conn=None):
        if ttl is None or ttl > self.max_ttl:
            ttl = self.max_ttl
        return await super().set(key, value, ttl=ttl, _cas_token=_cas_token, _conn=_conn)

    async def multi_set(self, pairs, ttl=None, dumps_fn=None, namespace=None, _conn=None):
        if ttl is None or ttl > self.max_ttl:
            ttl = self.max_ttl
        return await super().multi_set(pairs, ttl=ttl, dumps_fn=dumps_fn, namespace=namespace, _conn=_conn)

    async def expire(self, key, ttl, namespace=None, _conn=None):
        if ttl is None or ttl > self.max_ttl:
            ttl = self.max_ttl
        return await super().expire(key, ttl, namespace=namespace, _conn=_conn)
