# -*- coding: utf-8 -*-
import pytest
from jussi.cache.backends.max_ttl import SimplerMaxTTLMemoryCache

from .conftest import make_request
dummy_request = make_request()


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_clear(cache_cls):
    cache = cache_cls()
    await cache.clear()
    assert await cache.get('key') is None
    await cache.set('key', 'value', expire_time=None)
    assert await cache.get('key') == 'value'
    await cache.clear()
    assert await cache.get('key') is None


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_set_get(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', expire_time=None)
    assert await cache.get('key') == 'value'


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_multi_get(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.set('key', 'value', expire_time=None)
    await cache.set('key2', 'value2', expire_time=None)

    assert await cache.multi_get(['key', 'key2']) == ['value', 'value2']


@pytest.mark.parametrize('cache_cls', [SimplerMaxTTLMemoryCache])
async def test_cache_multi_set(cache_cls):
    cache = cache_cls()
    await cache.clear()
    await cache.multi_set([('key', 'value', 180), ('key2', 'value2', 180)])

    assert await cache.get('key') == 'value'
    assert await cache.get('key2') == 'value2'
