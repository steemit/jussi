# -*- coding: utf-8 -*-
from time import perf_counter
from typing import List
from typing import NoReturn
from typing import Tuple
from typing import TypeVar

import structlog

logger = structlog.get_logger(__name__)

MEMORY_CACHE_MAX_TTL = 180
MEMORY_CACHE_MAX_SIZE = 2000


CacheTTL = TypeVar('TTL', int, type(None))
CacheKey = str
CacheKeys = List[CacheKey]
CacheValue = TypeVar('CacheValue', int, float, str, dict)
CachePair = Tuple[CacheKey, CacheValue]
CacheTriplet = Tuple[CacheKey, CacheValue, CacheTTL]
CacheTriplets = List[CacheTriplet]
CacheResult = TypeVar('CacheValue', int, float, str, dict, type(None))
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

    def multi_gets(self, keys: CacheKeys) -> CacheResults:
        return [self.gets(k) for k in keys]

    async def multi_get(self, keys: CacheKeys) -> CacheResults:
        return [self.gets(k) for k in keys]

    def sets(self, key: CacheKey, value: CacheValue, ex: CacheTTL=None) -> NoReturn:
        if ex is None or ex > self._max_ttl:
            ex = self._max_ttl
        self.prune()
        self._cache[key] = (perf_counter() + ex), value
        return

    async def set(self, key: CacheKey, value: CacheValue, ex: CacheTTL=None) -> NoReturn:
        return self.sets(key, value, ex=ex)

    def multi_sets(self, triplets: CacheTriplets) -> NoReturn:
        _ = [self.sets(k, v, ttl) for k, v, ttl in triplets]
        return

    async def multi_set(self, triplets: CacheTriplets) -> NoReturn:
        _ = [self.sets(k, v, ttl) for k, v, ttl in triplets]
        return

    def deletes(self, key: CacheKey) -> NoReturn:
        if key in self._cache:
            del self._cache[key]

    async def delete(self, key: CacheKey) -> NoReturn:
        if key in self._cache:
            del self._cache[key]

    def prune(self) -> NoReturn:
        now = perf_counter()
        pruned = []
        for k, v in self._items:
            timestamp, result = self._cache[k]
            if timestamp - now < 0:
                pruned.append(k)
        if pruned:
            for k in pruned:
                del self._cache[k]
        elif len(self._items) >= self._max_size:
            keys = tuple(self._cache.keys())
            del self._cache[keys[0]]
        return

    def clears(self) -> NoReturn:
        self._cache = {}

    async def clear(self) -> NoReturn:
        return self.clears()
