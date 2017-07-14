# -*- coding: utf-8 -*-
import asyncio
import hashlib
import logging
from typing import Any
from typing import Optional

import aiocache
import aiocache.plugins

from jussi.serializers import CompressionSerializer
from jussi.typedefs import HTTPRequest
from jussi.typedefs import JussiAttrs
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import WebApp
from jussi.utils import ignore_errors_async

logger = logging.getLogger('sanic')

DEFAULT_TTL = 3
NO_CACHE_TTL = -1
NO_EXPIRE_TTL = 0

# add individual method cache settings here
METHOD_CACHE_SETTINGS = (('get_block', 'steemd_websocket_url', NO_EXPIRE_TTL),
                         ('get_block_header', 'steemd_websocket_url',
                          NO_EXPIRE_TTL), ('get_global_dynamic_properties',
                                           'steemd_websocket_url', 1))


# pylint: disable=unused-argument
def setup_caches(app: WebApp, loop) -> Any:
    logger.info('before_server_start -> setup_cache')
    args = app.config.args

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
        }
    }
    redis_cache_config = {
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
    if args.redis_host:
        caches_config.update(redis_cache_config)

    aiocache.caches.set_config(caches_config)

    # only use redis if we can really talk to it
    '''
    try:
        cache = aiocache.caches.get('redis')
        await cache.set('test', b'testval')
        val = await cache.get('test')
        logger.debug('before_server_start -> setup_cache val=%s', val)
        assert val == b'testval'
    except ConnectionRefusedError:
        logger.error('Unable to use redis (was a setting not defined?)')
        del caches_config['redis']
        aiocache.caches.set_config(caches_config)
    except Exception as e:
        logger.exception('Unable to use redis (was a setting not defined?)')
        del caches_config['redis']
        aiocache.caches.set_config(caches_config)
    '''
    return aiocache.caches


# pylint: enable=unused-argument


def jsonrpc_cache_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    if isinstance(single_jsonrpc_request.get('params'), dict):
        # the params dict should already be sorted, so no need to sort again
        params = tuple(sorted(single_jsonrpc_request['params'].items()))
    else:
        params = tuple(single_jsonrpc_request.get('params', []))
    return str(
        hashlib.sha1(('%s%s' % (params, single_jsonrpc_request['method'])
                      ).encode()).hexdigest())


@ignore_errors_async
async def cache_get(request: HTTPRequest,
                    jussi_attrs: JussiAttrs) -> Optional[bytes]:
    caches = request.app.config.caches
    logger.debug('cache.get(%s)', jussi_attrs.key)

    # happy eyeballs approach supports use of multiple caches, eg, SimpleMemoryCache and RedisCache
    for result in asyncio.as_completed(
        [cache.get(jussi_attrs.key) for cache in caches]):
        response = await result
        if response:
            logger.debug('cache --> %s', response)
            return response


@ignore_errors_async
async def cache_set(request: HTTPRequest, value,
                    jussi_attrs: JussiAttrs) -> None:
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


async def cache_json_response(request: HTTPRequest,
                              value: dict,
                              jussi_attrs: JussiAttrs) -> None:
    """Don't cache error responses

    Args:
        app: object
        value: str || bytes
        jussi_attrs: namedtuple

    Returns:

    """
    if 'error' in value:
        logger.error(
            'jsonrpc error %s in response from upstream %s, skipping cache',
            value['error'], jussi_attrs.upstream_url)
        return
    else:
        asyncio.ensure_future(cache_set(request, value, jussi_attrs))
