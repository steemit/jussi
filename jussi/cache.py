# -*- coding: utf-8 -*-
import asyncio
import hashlib
import logging

import aiocache
import aiocache.plugins
import ujson

from jussi.serializers import CompressionSerializer

logger = logging.getLogger('sanic')


# pylint: disable=unused-argument
async def setup_caches(app, loop):
    logger.info('before_server_start -> setup_cache')
    args = app.config.args
    # only use redis if we can really talk to it

    caches_config = {
        'default': {
            'cache':
            aiocache.SimpleMemoryCache,
            'serializer': {
                'class': CompressionSerializer
            },
            'plugins': [{
                'class': aiocache.plugins.HitMissRatioPlugin
            }, {
                'class': aiocache.plugins.TimingPlugin
            }]
        },
        'redis': {
            'cache':
            aiocache.RedisCache,
            'endpoint':
            args.redis_host,
            'port':
            args.redis_port,
            'timeout':
            3,
            'serializer': {
                'class': CompressionSerializer
            },
            'plugins': [{
                'class': aiocache.plugins.HitMissRatioPlugin
            }, {
                'class': aiocache.plugins.TimingPlugin
            }]
        }
    }
    aiocache.caches.set_config(caches_config)
    try:
        cache = aiocache.caches.get('redis')

        await cache.set('test', b'testval')
        val = await cache.get('test')
        logger.debug('before_server_start -> setup_cache val=%s', val)
        assert val == b'testval'
    except Exception as e:
        logger.exception(e)
        logger.error(
            'Unable to use redis (was a setting not defined?), using in-memory cache instead...'
        )
        del caches_config['redis']
        aiocache.caches.set_config(caches_config)
    return aiocache.caches


# pylint: enable=unused-argument


def jsonrpc_cache_key(single_jsonrpc_request):
    if isinstance(single_jsonrpc_request.get('params'), dict):
        # the params dict should already be sorted, so no need to sort again
        params = tuple(single_jsonrpc_request['params'].items())
    else:
        params = tuple(single_jsonrpc_request.get('params', []))

    return str(
        hashlib.sha1(('%s%s' % (params, single_jsonrpc_request['method'])
                      ).encode()).hexdigest())


async def cache_get(request, jussi_attrs):
    caches = request.app.config.caches
    logger.debug('cache.get(%s)', jussi_attrs.key)

    # happy eyeballs approach supports use of multiple caches, eg, SimpleMemoryCache and RedisCache
    for result in asyncio.as_completed(
        [cache.get(jussi_attrs.key) for cache in caches]):
        response = await result
        if response:
            logger.debug(logger.debug('cache --> %s', response))
            return response


async def cache_set(request, value, jussi_attrs):
    # ttl of -1 means don't cache
    ttl = jussi_attrs.ttl

    if ttl < 0:
        logger.debug('skipping non-cacheable value %s', value)
        return
    elif ttl == 0:
        ttl = None
    caches = request.app.config.caches
    logger.debug('cache.set(%s, %s, ttl=%s)', jussi_attrs.key, value, ttl)
    for cache in caches:
        # avoid using too much memory, especially beause there may be os.cpu_count() instances running
        if isinstance(cache, aiocache.SimpleMemoryCache) and ttl >= 0:
            ttl = 60
        asyncio.ensure_future(cache.set(jussi_attrs.key, value, ttl=ttl))


async def cache_json_response(request, value, jussi_attrs):
    """Don't cache error responses

    Args:
        app: object
        value: str || bytes
        jussi_attrs: namedtuple

    Returns:

    """
    try:
        if isinstance(value, bytes):
            parsed = ujson.loads(value.decode())
        else:
            parsed = ujson.loads(value)

    except Exception as e:
        logger.error(
            'json parse error %s in response from upstream %s, skipping cache',
            e, jussi_attrs.upstream_url)
        return
    if 'error' in parsed:
        logger.error(
            'jsonrpc error %s in response from upstream %s, skipping cache',
            parsed['error'], jussi_attrs.upstream_url)
        return
    else:
        asyncio.ensure_future(cache_set(request, value, jussi_attrs))
