# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Any
from typing import AnyStr
from typing import List
from typing import Optional
from typing import Union

import aiocache
import aiocache.plugins
from funcy.decorators import decorator

import cytoolz
import jussi.jsonrpc_method_cache_settings
from jussi.serializers import CompressionSerializer
from jussi.typedefs import BatchJsonRpcRequest
from jussi.typedefs import BatchJsonRpcResponse
from jussi.typedefs import CachedBatchResponse
from jussi.typedefs import CachedSingleResponse
from jussi.typedefs import HTTPRequest
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import SingleJsonRpcResponse
from jussi.typedefs import WebApp
from jussi.utils import ignore_errors_async
from jussi.utils import is_jsonrpc_error_response
from jussi.utils import method_urn

logger = logging.getLogger('sanic')

Caches = List[Union[aiocache.SimpleMemoryCache,aiocache.RedisCache]]


@decorator
async def cacher(call):
    # pylint: disable=protected-access
    sanic_http_request = call.sanic_http_request
    jsonrpc_request = call.jsonrpc_request
    skip_cache_get = call._kwargs.get('skip_cacher_get',False)
    skip_cache_set = call._kwargs.get('skip_cacher_set',False)
    if 'skip_cacher_get' in call._kwargs:
        del call._kwargs['skip_cacher_get']
    if 'skip_cacher_set' in call._kwargs:
        del call._kwargs['skip_cacher_set']

    if not skip_cache_get:
        logger.debug('cacher querying caches for request',)
        json_response = await cache_get(sanic_http_request,
                                    jsonrpc_request)
        if json_response:
            return json_response
    else:
        logger.debug('cacher not querying caches for request')

    json_response = await call()

    if not skip_cache_set:
        logger.debug('cacher caching result')
        asyncio.ensure_future(
            cache_jsonrpc_response(sanic_http_request,
                                   jsonrpc_request,
                                   json_response))
    else:
        logger.debug('cacher not caching result')
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
async def cache_get(sanic_http_request: HTTPRequest,
                    single_jsonrpc_request: SingleJsonRpcRequest
                    ) -> Optional[dict]:
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    logger.debug('cache_get key=%s', key)


    # caches should be sorted from fastest to slowest, ie, [SimpleMemoryCache, RedisCache]
    for cache in caches:
        cached_response = await cache.get(key)
        if cached_response:
            logger.debug('cache_get response %s: %s', cache, cached_response)
            return merge_cached_response(cached_response, single_jsonrpc_request)
    logger.debug('cache_get miss with key=%s', key)


@ignore_errors_async
async def cache_set(sanic_http_request: HTTPRequest,
                    single_jsonrpc_request: SingleJsonRpcRequest,
                    value: Union[AnyStr, dict],
                    ttl=None,
                    **kwargs):
    last_irreversible_block_num = sanic_http_request.app.config.last_irreversible_block_num
    ttl = ttl or ttl_from_jsonrpc_request(single_jsonrpc_request,
                                          last_irreversible_block_num,
                                          value)
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    for cache in caches:
        if ttl == jussi.jsonrpc_method_cache_settings.NO_CACHE:
            logger.debug('skipping cache for ttl=%s value %s', ttl, value)
            return
        if isinstance(cache, aiocache.SimpleMemoryCache):
            in_memory_ttl = memory_cache_ttl(ttl)
            logger.debug('%s.set(%s, %s, ttl=%s)', cache, key, value, in_memory_ttl)
            asyncio.ensure_future(cache.set(key, value, ttl=convert_no_expire_ttl(in_memory_ttl), **kwargs))
        logger.debug('%s.set(%s, %s, ttl=%s)', cache, key, value, ttl)
        asyncio.ensure_future(cache.set(key, value, ttl=convert_no_expire_ttl(ttl), **kwargs))



async def cache_get_batch(caches: Caches, jsonrpc_batch_request:BatchJsonRpcRequest) -> BatchJsonRpcResponse:
    keys = list(map(jsonrpc_cache_key, jsonrpc_batch_request))
    batch_response = [None for req in jsonrpc_batch_request]
    for cache in caches:
        cached_responses = await cache.multi_get(keys)
        logger.debug('cache_get_batch cached_responses %s: %s', cache, cached_responses)
        batch_response = [new or old for old,new in zip(batch_response, cached_responses)]
        logger.debug('cache_get_batch cached_responses %s: %s', cache, cached_responses)
        if all(batch_response):
            # dont wait if we already have everything
            logger.debug('cache_get_batch all requests found in cache')
            return merge_cached_responses(jsonrpc_batch_request, batch_response)
        return merge_cached_responses(jsonrpc_batch_request, batch_response)



async def cache_jsonrpc_response(sanic_http_request: HTTPRequest,
                                 single_jsonrpc_request: SingleJsonRpcRequest,
                                 jsonrpc_response: SingleJsonRpcResponse) -> None:
    """Don't cache error responses
    """
    if is_jsonrpc_error_response(jsonrpc_response):
        logger.warning(
            'jsonrpc error in response from upstream %s, skipping cache',
            jsonrpc_response)
        return
    asyncio.ensure_future(cache_set(sanic_http_request, single_jsonrpc_request, jsonrpc_response))


def memory_cache_ttl(ttl: int, max_ttl=60) -> int:
    # avoid using too much memory, especially beause there may be
    # os.cpu_count() instances running
    if ttl > max_ttl:
        logger.debug('adjusting memory cache ttl from %s to %s', ttl, max_ttl)
        return max_ttl
    return ttl


def ttl_from_jsonrpc_request(
        single_jsonrpc_request: SingleJsonRpcRequest,
        last_irreversible_block_num: int = 0,
        jsonrpc_response: dict = None) -> int:
    urn = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    ttl = ttl_from_urn(urn)
    if ttl == jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE:
        ttl = irreversible_ttl(jsonrpc_response, last_irreversible_block_num)
    return ttl


def ttl_from_urn(urn: str) -> int:
    _, ttl = jussi.jsonrpc_method_cache_settings.TTLS.longest_prefix(urn)
    return ttl

def adjust_irreversible_ttl(jsonrpc_response:SingleJsonRpcRequest, last_irreversible_block_num: int, ttl: int) -> int:
    if ttl == jussi.jsonrpc_method_cache_settings.NO_EXPIRE_IF_IRREVERSIBLE:
        ttl = irreversible_ttl(jsonrpc_response, last_irreversible_block_num)
    return ttl

def convert_no_expire_ttl(ttl: int) -> Union[int, None]:
    if ttl == 0:
        return None
    return ttl

def irreversible_ttl(jsonrpc_response: dict = None,
                     last_irreversible_block_num: int = 0) -> int:
    try:
        jrpc_block_num = block_num_from_jsonrpc_response(jsonrpc_response)
        if  last_irreversible_block_num < jrpc_block_num:
            logger.debug('skipping cache for block_num > last_irreversible')
            return jussi.jsonrpc_method_cache_settings.NO_CACHE
        return jussi.jsonrpc_method_cache_settings.NO_EXPIRE
    except Exception as e:
        logger.warning('Unable to cache using last irreversible block: %s', e)
        return jussi.jsonrpc_method_cache_settings.NO_CACHE


def block_num_from_jsonrpc_response(jsonrpc_response: SingleJsonRpcRequest = None) -> int:
    # pylint: disable=no-member
    block_id = cytoolz.get_in(['result','block_id'],jsonrpc_response)
    return block_num_from_id(block_id)

def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)

def merge_cached_response(cached_response: CachedSingleResponse, jsonrpc_request:SingleJsonRpcRequest) -> SingleJsonRpcRequest:
    if 'id' in jsonrpc_request:
        cached_response['id'] = jsonrpc_request['id']
    else:
        del cached_response['id']
    return cached_response

def merge_cached_responses(jsonrpc_batch_request: BatchJsonRpcRequest, cached_responses: CachedBatchResponse) -> CachedBatchResponse:
    merged = []
    for i,response in enumerate(cached_responses):
        if response:
            merged.append(merge_cached_response(response, jsonrpc_batch_request[i]))
        else:
            merged.append(response)
    return merged
