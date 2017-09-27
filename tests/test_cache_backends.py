# -*- coding: utf-8 -*-
import pytest
from jussi.cache.backends import SimpleMaxTTLMemoryCache


@pytest.mark.parametrize('cache_cls', [SimpleMaxTTLMemoryCache])
async def test_cache_clear(cache_cls):
    cache = cache_cls()
    await cache.clear()
    assert await cache.get('key') == None
    await cache.set('key', 'value', ttl=None)
    assert await cache.get('key') == 'value'
    await cache.clear()
    assert await cache.get('key') == None


@pytest.mark.parametrize('cache_cls', [SimpleMaxTTLMemoryCache])
async def test_cache_set_get(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', ttl=None)
    assert await cache.get('key') == 'value'


@pytest.mark.parametrize('cache_cls', [SimpleMaxTTLMemoryCache])
async def test_cache_multi_get(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', ttl=None)
    await cache.set('key2', 'value2', ttl=None)

    assert await cache.multi_get(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache_cls', [SimpleMaxTTLMemoryCache])
async def test_cache_multi_set(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.multi_set([('key', 'value'), ('key2', 'value2')])

    assert await cache.get('key') == 'value'
    assert await cache.get('key2') == 'value2'
