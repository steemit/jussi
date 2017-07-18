# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Any
from typing import AnyStr
from typing import Optional
from typing import Union

import aiocache
import aiocache.plugins
from funcy.decorators import decorator

import jussi.jsonrpc_method_cache_settings
from jussi.serializers import CompressionSerializer
from jussi.typedefs import HTTPRequest
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import WebApp
from jussi.utils import ignore_errors_async
from jussi.utils import method_urn

logger = logging.getLogger('sanic')


@decorator
async def cacher(call):
    sanic_http_request = call.sanic_http_request
    json_response = await cache_get(sanic_http_request)
    if json_response:
        return json_response
    json_response = await call()
    asyncio.ensure_future(
        cache_json_response(sanic_http_request, json_response))
    return json_response


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
    return aiocache.caches
    # pylint: enable=unused-argument


def jsonrpc_cache_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    return method_urn(single_jsonrpc_request)


@ignore_errors_async
async def cache_get(sanic_http_request: HTTPRequest) -> Optional[bytes]:
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=sanic_http_request.json)
    logger.debug('cache.get(%s)', key)

    # happy eyeballs approach supports use of multiple caches, eg, SimpleMemoryCache and RedisCache
    for result in asyncio.as_completed([cache.get(key) for cache in caches]):
        logger.debug('cache_get result: %s', result)
        response = await result
        logger.debug('cache_get response: %s', response)
        if response:
            logger.debug('cache --> %s', response)
            return response


@ignore_errors_async
async def cache_set(sanic_http_request: HTTPRequest,
                    value: Union[AnyStr, dict],
                    ttl=None,
                    **kwargs):
    ttl = ttl or ttl_from_jsonrpc_request(sanic_http_request.json)
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=sanic_http_request.json)
    for cache in caches:
        if isinstance(cache, aiocache.SimpleMemoryCache):
            ttl = memory_cache_ttl(ttl)
        if ttl == jussi.jsonrpc_method_cache_settings.NO_CACHE:
            logger.debug('skipping non-cacheable value %s', value)
            return
        logger.debug('cache.set(%s, %s, ttl=%s)', key, value, ttl)
        asyncio.ensure_future(cache.set(key, value, ttl=ttl, **kwargs))


async def cache_json_response(sanic_http_request: HTTPRequest,
                              value: dict) -> None:
    """Don't cache error responses
    """
    if 'error' in value:
        logger.error(
            'jsonrpc error in response from upstream %s, skipping cache',
            value)
        return
    asyncio.ensure_future(cache_set(sanic_http_request, value))


def memory_cache_ttl(ttl: int, max_ttl=60) -> Union[None, int]:
    # avoid using too much memory, especially beause there may be os.cpu_count() instances running
    if 0 < ttl < 60:
        logger.debug('adjusting memory cache ttl from %s to %s', ttl, max_ttl)
        ttl = max_ttl
    return ttl


def ttl_from_jsonrpc_request(
        single_jsonrpc_request: SingleJsonRpcRequest) -> int:
    urn = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    return ttl_from_urn(urn)


def ttl_from_urn(urn: str) -> int:
    _, ttl = jussi.jsonrpc_method_cache_settings.TTLS.longest_prefix(urn)
    return ttl
