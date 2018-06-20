# -*- coding: utf-8 -*-
import time
import pytest
from jussi.cache.backends.max_ttl import SimplerMaxTTLMemoryCache

from .conftest import make_request
dummy_request = make_request()


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_clear(cache_cls):
    cache = cache_cls()
    await cache.clear()
    assert await cache.get('key') is None
    await cache.set('key', 'value', None)
    assert await cache.get('key') == 'value'
    await cache.clear()
    assert await cache.get('key') is None


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_gets(cache_cls):
    cache = cache_cls()
    cache.sets('key', 'value', None)
    assert cache.gets('key') == 'value'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_get(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', None)
    assert await cache.get('key') == 'value'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_mgets(cache_cls):
    cache = cache_cls()
    cache.sets('key', 'value', None)
    cache.sets('key2', 'value2', None)
    assert cache.mgets(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_mget(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', None)
    await cache.set('key2', 'value2', None)
    assert await cache.mget(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_client_mget(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', None)
    await cache.set('key2', 'value2', None)
    assert await cache.client.mget(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_set_manys(cache_cls):
    cache = cache_cls()
    cache.set_manys({'key1': 'value1', 'key2': 'value2'}, None)
    assert cache.gets('key1') == 'value1'
    assert cache.gets('key2') == 'value2'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_set_many(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set_many({'key': 'value', 'key2': 'value2'}, 180)
    assert await cache.get('key') == 'value'
    assert await cache.get('key2') == 'value2'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_set_many(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set_many({'key': 'value', 'key2': 'value2'}, 180)
    assert await cache.get('key') == 'value'
    assert await cache.get('key2') == 'value2'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_deletes(cache_cls):
    cache = cache_cls()
    cache.sets('key', 'value', None)
    cache.deletes('key')
    assert cache.gets('key') is None


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_delete(cache_cls):
    cache = cache_cls()
    cache.sets('key', 'value', None)
    await cache.delete('key')
    assert cache.gets('key') is None


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_ttl_none(cache_cls):
    cache = cache_cls()
    now = time.perf_counter()
    cache.sets('key', 'value', None)
    timestamp, value = cache._cache['key']
    assert timestamp - (now + cache._max_ttl) < 5


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_ttl_expire(cache_cls):
    cache = cache_cls()
    cache.sets('key', 'value', 0)
    assert cache.gets('key') is None


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_ttl_large_ttl(cache_cls):
    cache = cache_cls()
    now = time.perf_counter()
    cache.sets('key', 'value', cache._max_ttl + 100)
    timestamp, value = cache._cache['key']
    assert timestamp - (now + cache._max_ttl) < 5


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
def test_cache_max_size(cache_cls):
    cache = cache_cls()
    max_size = cache._max_size
    for i in range(max_size + 10):
        cache.sets(f'{i}', 'value', cache._max_ttl + 100)
    assert len(cache._cache) == max_size
