# -*- coding: utf-8 -*-
# -*- coding: utf-8 -*-

import asyncio

from aiocache.backends.memory import SimpleMemoryBackend
from aiocache.base import BaseCache
from aiocache.serializers import NullSerializer

MEMORY_CACHE_MAX_TTL = 180



class SimpleMemoryBackend2:
    """
    Wrapper around dict operations to use it as a cache backend
    """

    _cache = {}
    _handlers = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _get(self, key, encoding="utf-8", _conn=None):
        return SimpleMemoryBackend2._cache.get(key)

    async def _gets(self, key, encoding="utf-8", _conn=None):
        return await self._get(key, encoding=encoding, _conn=_conn)

    async def _multi_get(self, keys, encoding="utf-8", _conn=None):
        return [SimpleMemoryBackend2._cache.get(key) for key in keys]

    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        if _cas_token is not None and _cas_token != SimpleMemoryBackend2._cache.get(key):
            return 0
        SimpleMemoryBackend2._cache[key] = value
        if ttl:
            loop = asyncio.get_event_loop()
            SimpleMemoryBackend2._handlers[key] = loop.call_later(ttl, self.__delete, key)
        return True

    async def _multi_set(self, pairs, ttl=None, _conn=None):
        for key, value in pairs:
            await self._set(key, value, ttl=ttl)
        return True

    async def _add(self, key, value, ttl=None, _conn=None):
        if key in SimpleMemoryBackend2._cache:
            raise ValueError(
                "Key {} already exists, use .set to update the value".format(key))

        await self._set(key, value, ttl=ttl)
        return True

    async def _exists(self, key, _conn=None):
        return key in SimpleMemoryBackend2._cache

    async def _increment(self, key, delta, _conn=None):
        if key not in SimpleMemoryBackend2._cache:
            SimpleMemoryBackend2._cache[key] = delta
        else:
            try:
                SimpleMemoryBackend2._cache[key] = int(SimpleMemoryBackend2._cache[key]) + delta
            except ValueError:
                raise TypeError("Value is not an integer") from None
        return SimpleMemoryBackend2._cache[key]

    async def _expire(self, key, ttl, _conn=None):
        if key in SimpleMemoryBackend2._cache:
            handle = SimpleMemoryBackend2._handlers.pop(key, None)
            if handle:
                handle.cancel()
            if ttl:
                loop = asyncio.get_event_loop()
                SimpleMemoryBackend2._handlers[key] = loop.call_later(ttl, self.__delete, key)
            return True

        return False

    async def _delete(self, key, _conn=None):
        return self.__delete(key)

    async def _clear(self, namespace=None, _conn=None):
        if namespace:
            for key in list(SimpleMemoryBackend2._cache):
                if key.startswith(namespace):
                    self.__delete(key)
        else:
            SimpleMemoryBackend2._cache = {}
            SimpleMemoryBackend2._handlers = {}
        return True

    async def _raw(self, command, *args, encoding="utf-8", _conn=None, **kwargs):
        return getattr(SimpleMemoryBackend2._cache, command)(*args, **kwargs)

    async def _redlock_release(self, key, value):
        if SimpleMemoryBackend2._cache.get(key) == value:
            SimpleMemoryBackend2._cache.pop(key)
            return 1
        return 0

    @classmethod
    def __delete(cls, key):
        if SimpleMemoryBackend2._cache.pop(key, None):
            handle = SimpleMemoryBackend2._handlers.pop(key, None)
            if handle:
                handle.cancel()
            return 1

        return 0


class SimpleMemoryBackend3:
    """
    Wrapper around dict operations to use it as a cache backend
    """

    _cache = {}
    _handlers = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _get(self, key, encoding="utf-8", _conn=None):
        return SimpleMemoryBackend3._cache.get(key)

    async def _gets(self, key, encoding="utf-8", _conn=None):
        return await self._get(key, encoding=encoding, _conn=_conn)

    async def _multi_get(self, keys, encoding="utf-8", _conn=None):
        return [SimpleMemoryBackend3._cache.get(key) for key in keys]

    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        if _cas_token is not None and _cas_token != SimpleMemoryBackend3._cache.get(key):
            return 0
        SimpleMemoryBackend3._cache[key] = value
        if ttl:
            loop = asyncio.get_event_loop()
            SimpleMemoryBackend3._handlers[key] = loop.call_later(ttl, self.__delete, key)
        return True

    async def _multi_set(self, pairs, ttl=None, _conn=None):
        for key, value in pairs:
            await self._set(key, value, ttl=ttl)
        return True

    async def _add(self, key, value, ttl=None, _conn=None):
        if key in SimpleMemoryBackend3._cache:
            raise ValueError(
                "Key {} already exists, use .set to update the value".format(key))

        await self._set(key, value, ttl=ttl)
        return True

    async def _exists(self, key, _conn=None):
        return key in SimpleMemoryBackend3._cache

    async def _increment(self, key, delta, _conn=None):
        if key not in SimpleMemoryBackend3._cache:
            SimpleMemoryBackend3._cache[key] = delta
        else:
            try:
                SimpleMemoryBackend3._cache[key] = int(SimpleMemoryBackend3._cache[key]) + delta
            except ValueError:
                raise TypeError("Value is not an integer") from None
        return SimpleMemoryBackend3._cache[key]

    async def _expire(self, key, ttl, _conn=None):
        if key in SimpleMemoryBackend3._cache:
            handle = SimpleMemoryBackend3._handlers.pop(key, None)
            if handle:
                handle.cancel()
            if ttl:
                loop = asyncio.get_event_loop()
                SimpleMemoryBackend3._handlers[key] = loop.call_later(ttl, self.__delete, key)
            return True

        return False

    async def _delete(self, key, _conn=None):
        return self.__delete(key)

    async def _clear(self, namespace=None, _conn=None):
        if namespace:
            for key in list(SimpleMemoryBackend3._cache):
                if key.startswith(namespace):
                    self.__delete(key)
        else:
            SimpleMemoryBackend3._cache = {}
            SimpleMemoryBackend3._handlers = {}
        return True

    async def _raw(self, command, *args, encoding="utf-8", _conn=None, **kwargs):
        return getattr(SimpleMemoryBackend3._cache, command)(*args, **kwargs)

    async def _redlock_release(self, key, value):
        if SimpleMemoryBackend3._cache.get(key) == value:
            SimpleMemoryBackend3._cache.pop(key)
            return 1
        return 0

    @classmethod
    def __delete(cls, key):
        if SimpleMemoryBackend3._cache.pop(key, None):
            handle = SimpleMemoryBackend3._handlers.pop(key, None)
            if handle:
                handle.cancel()
            return 1

        return 0


class SimpleMemoryBackend4:
    """
    Wrapper around dict operations to use it as a cache backend
    """

    _cache = {}
    _handlers = {}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def _get(self, key, encoding="utf-8", _conn=None):
        return SimpleMemoryBackend4._cache.get(key)

    async def _gets(self, key, encoding="utf-8", _conn=None):
        return await self._get(key, encoding=encoding, _conn=_conn)

    async def _multi_get(self, keys, encoding="utf-8", _conn=None):
        return [SimpleMemoryBackend4._cache.get(key) for key in keys]

    async def _set(self, key, value, ttl=None, _cas_token=None, _conn=None):
        if _cas_token is not None and _cas_token != SimpleMemoryBackend4._cache.get(key):
            return 0
        SimpleMemoryBackend4._cache[key] = value
        if ttl:
            loop = asyncio.get_event_loop()
            SimpleMemoryBackend4._handlers[key] = loop.call_later(ttl, self.__delete, key)
        return True

    async def _multi_set(self, pairs, ttl=None, _conn=None):
        for key, value in pairs:
            await self._set(key, value, ttl=ttl)
        return True

    async def _add(self, key, value, ttl=None, _conn=None):
        if key in SimpleMemoryBackend4._cache:
            raise ValueError(
                "Key {} already exists, use .set to update the value".format(key))

        await self._set(key, value, ttl=ttl)
        return True

    async def _exists(self, key, _conn=None):
        return key in SimpleMemoryBackend4._cache

    async def _increment(self, key, delta, _conn=None):
        if key not in SimpleMemoryBackend4._cache:
            SimpleMemoryBackend4._cache[key] = delta
        else:
            try:
                SimpleMemoryBackend4._cache[key] = int(SimpleMemoryBackend4._cache[key]) + delta
            except ValueError:
                raise TypeError("Value is not an integer") from None
        return SimpleMemoryBackend4._cache[key]

    async def _expire(self, key, ttl, _conn=None):
        if key in SimpleMemoryBackend4._cache:
            handle = SimpleMemoryBackend4._handlers.pop(key, None)
            if handle:
                handle.cancel()
            if ttl:
                loop = asyncio.get_event_loop()
                SimpleMemoryBackend4._handlers[key] = loop.call_later(ttl, self.__delete, key)
            return True

        return False

    async def _delete(self, key, _conn=None):
        return self.__delete(key)

    async def _clear(self, namespace=None, _conn=None):
        if namespace:
            for key in list(SimpleMemoryBackend4._cache):
                if key.startswith(namespace):
                    self.__delete(key)
        else:
            SimpleMemoryBackend4._cache = {}
            SimpleMemoryBackend4._handlers = {}
        return True

    async def _raw(self, command, *args, encoding="utf-8", _conn=None, **kwargs):
        return getattr(SimpleMemoryBackend4._cache, command)(*args, **kwargs)

    async def _redlock_release(self, key, value):
        if SimpleMemoryBackend4._cache.get(key) == value:
            SimpleMemoryBackend4._cache.pop(key)
            return 1
        return 0

    @classmethod
    def __delete(cls, key):
        if SimpleMemoryBackend4._cache.pop(key, None):
            handle = SimpleMemoryBackend4._handlers.pop(key, None)
            if handle:
                handle.cancel()
            return 1
        return 0



class SimpleMemoryCache2(SimpleMemoryBackend2, BaseCache):
    def __init__(self, serializer=None, **kwargs):
        super().__init__(**kwargs)
        self.serializer = serializer or NullSerializer()

class SimpleMemoryCache3(SimpleMemoryBackend3, BaseCache):
    def __init__(self, serializer=None, **kwargs):
        super().__init__(**kwargs)
        self.serializer = serializer or NullSerializer()

class SimpleMemoryCache4(SimpleMemoryBackend4, BaseCache):
    def __init__(self, serializer=None, **kwargs):
        super().__init__(**kwargs)
        self.serializer = serializer or NullSerializer()
