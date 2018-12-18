# -*- coding: utf-8 -*-
from time import perf_counter
from typing import Dict
from typing import List
from typing import NoReturn
from typing import Optional
from typing import Tuple
from typing import TypeVar

import structlog

logger = structlog.get_logger(__name__)

MEMORY_CACHE_MAX_TTL = 180
MEMORY_CACHE_MAX_SIZE = 2000


CacheTTLValue = TypeVar('CacheTTL', int, float, type(None))
CacheKey = str
CacheKeys = List[CacheKey]
CacheValue = TypeVar('CacheValue', int, float, str, dict)
CachePair = Tuple[CacheKey, CacheValue]
CachePairs = Dict[CacheKey, CacheValue]
CacheResultValue = TypeVar('CacheValue', int, float, str, dict)
CacheResult = Optional[CacheResultValue]
CacheResults = List[CacheResult]


class SimplerMaxTTLMemoryCache:
    def __init__(self, max_ttl: int = None, max_size: int=None):

        self._cache = {}

        # these are dynamic views
        self._keys = self._cache.keys()
        self._values = self._cache.values()
        self._items = self._cache.items()
        self._max_ttl = max_ttl or MEMORY_CACHE_MAX_TTL
        self._max_size = max_size or MEMORY_CACHE_MAX_SIZE

    def gets(self, key: CacheKey) -> CacheResult:
        if key in self._cache:
            timestamp, result = self._cache[key]
            if timestamp - perf_counter() > 0:
                return result
            else:
                del self._cache[key]
        return None

    async def get(self, key: CacheKey) -> CacheResult:
        return self.gets(key)

    def mgets(self, keys: CacheKeys) -> CacheResults:
        return [self.gets(k) for k in keys]

    async def mget(self, keys: CacheKeys) -> CacheResults:
        return [self.gets(k) for k in keys]

    def sets(self, key: CacheKey, value: CacheValue, expire_time: CacheTTLValue) -> NoReturn:
        if expire_time is None or expire_time > self._max_ttl:
            expire_time = self._max_ttl
        self.prune()
        self._cache[key] = (perf_counter() + expire_time), value
        return

    async def set(self, key: CacheKey, value: CacheValue, expire_time: CacheTTLValue) -> NoReturn:
        return self.sets(key, value, expire_time)

    def set_manys(self, data: CachePairs, expire_time: CacheTTLValue) -> NoReturn:
        _ = [self.sets(k, v, expire_time) for k, v, in data.items()]
        return

    async def set_many(self, data: CachePairs, expire_time: CacheTTLValue) -> NoReturn:
        _ = [self.sets(k, v, expire_time) for k, v, in data.items()]
        return

    def deletes(self, key: CacheKey) -> NoReturn:
        if key in self._cache:
            del self._cache[key]

    async def delete(self, key: CacheKey) -> NoReturn:
        if key in self._cache:
            del self._cache[key]

    def prune(self) -> NoReturn:
        now = perf_counter()
        pruned = [k for k, v in self._items if (v[0] - now) < 0]
        for k in pruned:
            del self._cache[k]
        if len(self._items) >= self._max_size:
            del self._cache[next(iter(self._cache))]
        return

    def clears(self) -> NoReturn:
        self._cache = {}
        return

    async def clear(self) -> NoReturn:
        return self.clears()
