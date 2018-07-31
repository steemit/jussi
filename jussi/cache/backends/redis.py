# -*- coding: utf-8 -*-
from zlib import compress
from zlib import decompress
from typing import Dict
from typing import List
from typing import NoReturn
from typing import Optional
from typing import Tuple
from typing import TypeVar


from ujson import dumps
from ujson import loads

CacheTTLValue = TypeVar('CacheTTL', int, float, type(None))
CacheKey = str
CacheKeys = List[CacheKey]
CacheValue = TypeVar('CacheValue', int, float, str, dict)
CachePair = Tuple[CacheKey, CacheValue]
CachePairs = Dict[CacheKey, CacheValue]
CacheResultValue = TypeVar('CacheValue', int, float, str, dict)
CacheResult = Optional[CacheResultValue]
CacheResults = List[CacheResult]


class Cache:
    """cache provides basic function"""

    def __init__(self, client):
        self.client = client

    # pylint: disable=no-self-use
    def _pack(self, value) -> bytes:
        return compress(dumps(value, ensure_ascii=False).encode('utf8'))

    def _unpack(self, value: bytes) -> CacheResult:
        if not value:
            return None
        return loads(decompress(value))

    # pylint: enable=no-self-use

    async def get(self, key: CacheKey) -> CacheResult:
        res = await self.client.get(key)
        if res:
            return self._unpack(res)
        return None

    async def set(self, key: str, value, expire_time: CacheTTLValue=None) -> NoReturn:
        value = self._pack(value)
        await self.client.set(key, value, ex=expire_time)

    async def set_many(self, data: CachePairs, expire_time: CacheTTLValue=None) -> NoReturn:
        async with await self.client.pipeline() as pipeline:
            for key, value in data.items():
                value = self._pack(value)
                await pipeline.set(key, value, expire_time)
            return await pipeline.execute()

    async def mget(self, keys: CacheKeys) -> CacheResults:
        return [self._unpack(r) for r in await self.client.mget(keys)]

    async def clear(self):
        return await self.client.clear()

    async def close(self):
        self.client.connection_pool.disconnect()

    async def delete(self, key):
        await self.client.delete(key)


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class MockClient:
    def __init__(self, cache):
        self.cache = cache
        self.connection_pool = AttrDict()
        self.connection_pool.disconnect = lambda: None

    async def execute(self):
        pass

    async def set(self, key, value, ex: CacheTTLValue=None) -> NoReturn:
        self.cache.sets(key, value, ex)

    async def get(self, key) -> CacheResult:
        return self.cache.gets(key)

    async def mget(self, keys) -> CacheResults:
        return self.cache.mgets(keys)

    async def pipeline(self):
        return self

    async def clear(self):
        self.cache.clears()

    async def delete(self, key):
        self.cache.deletes(key)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass
