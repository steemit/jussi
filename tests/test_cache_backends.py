# -*- coding: utf-8 -*-

import time
import pytest
from jussi.cache.backends.max_ttl import SimplerMaxTTLMemoryCache

from .conftest import make_request
from .conftest import build_mocked_cache
dummy_request = make_request()


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache(), build_mocked_cache()])
async def test_cache_clear(cache):
    await cache.clear()
    assert await cache.get('key') is None
    await cache.set('key', 'value', None)
    assert await cache.get('key') == 'value'
    await cache.clear()
    assert await cache.get('key') is None


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_gets(cache):
    cache.sets('key', 'value', None)
    assert cache.gets('key') == 'value'


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache(), build_mocked_cache()])
async def test_cache_get(cache):
    await cache.clear()
    await cache.set('key', 'value', None)
    assert await cache.get('key') == 'value'


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_mgets(cache):
    cache.sets('key', 'value', None)
    cache.sets('key2', 'value2', None)
    assert cache.mgets(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache(), build_mocked_cache()])
async def test_cache_mget(cache):
    await cache.clear()
    await cache.set('key', 'value', None)
    await cache.set('key2', 'value2', None)
    assert await cache.mget(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_set_manys(cache):
    cache.set_manys({'key1': 'value1', 'key2': 'value2'}, None)
    assert cache.gets('key1') == 'value1'
    assert cache.gets('key2') == 'value2'


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache(), build_mocked_cache()])
async def test_cache_set_many(cache):
    await cache.clear()
    await cache.set_many({'key': 'value', 'key2': 'value2'}, 180)
    assert await cache.get('key') == 'value'
    assert await cache.get('key2') == 'value2'


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_deletes(cache):
    cache.sets('key', 'value', None)
    cache.deletes('key')
    assert cache.gets('key') is None


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache(), build_mocked_cache()])
async def test_cache_delete(cache):
    await cache.set('key', 'value', None)
    await cache.delete('key')
    assert await cache.get('key') is None


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_ttl_none(cache):
    now = time.perf_counter()
    cache.sets('key', 'value', None)
    timestamp, value = cache._cache['key']
    assert timestamp - (now + cache._max_ttl) < 5


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_ttl_expire(cache):
    cache.sets('key', 'value', 0)
    assert cache.gets('key') is None


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_ttl_large_ttl(cache):
    now = time.perf_counter()
    cache.sets('key', 'value', cache._max_ttl + 100)
    timestamp, value = cache._cache['key']
    assert timestamp - (now + cache._max_ttl) < 5


@pytest.mark.parametrize('cache', [SimplerMaxTTLMemoryCache()])
def test_cache_max_size(cache):
    max_size = cache._max_size
    for i in range(max_size + 10):
        cache.sets(f'{i}', 'value', cache._max_ttl + 100)
    assert len(cache._cache) == max_size
