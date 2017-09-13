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
import cytoolz
from funcy.decorators import decorator

import jussi.jsonrpc_method_cache_settings
from jussi.jsonrpc_method_cache_settings import TTL
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

logger = logging.getLogger(__name__)

Caches = List[Union[aiocache.SimpleMemoryCache, aiocache.RedisCache]]


@decorator
async def cacher(call):
    # pylint: disable=protected-access
    sanic_http_request = call.sanic_http_request
    jsonrpc_request = call.jsonrpc_request
    skip_cache_get = call._kwargs.get('skip_cacher_get', False)
    skip_cache_set = call._kwargs.get('skip_cacher_set', False)
    if 'skip_cacher_get' in call._kwargs:
        del call._kwargs['skip_cacher_get']
    if 'skip_cacher_set' in call._kwargs:
        del call._kwargs['skip_cacher_set']

    if not skip_cache_get:
        logger.debug('cacher querying caches for request', )
        json_response = await cache_get(sanic_http_request, jsonrpc_request)
        if json_response:
            return json_response
    else:
        logger.debug('cacher not querying caches for request')

    json_response = await call()

    if not skip_cache_set:
        logger.debug('cacher caching result')
        await cache_jsonrpc_response(sanic_http_request, jsonrpc_request,
                                     json_response)
    else:
        logger.debug('cacher not caching result')
    return json_response


# pylint: disable=unused-argument
def setup_caches(app: WebApp, loop) -> Any:
    logger.info('before_server_start -> cache.setup_cache')
    args = app.config.args

    caches_config = {
        'default': {
            'cache': 'jussi.cache_backends.SimpleLRUMemoryCache',
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
                'class': 'jussi.serializers.CompressionSerializer'
            },
            'plugins': [{
                'class': aiocache.plugins.HitMissRatioPlugin
            }, {
                'class': aiocache.plugins.TimingPlugin
            }]
        }
    }
    if not args.redis_host:
        del caches_config['redis']
    logger.debug(f'caches config: {aiocache.caches.get_config()}')
    return caches_config
    # pylint: enable=unused-argument


def jsonrpc_cache_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    return method_urn(single_jsonrpc_request)


@ignore_errors_async
async def cache_get(
        sanic_http_request: HTTPRequest,
        single_jsonrpc_request: SingleJsonRpcRequest) -> Optional[dict]:
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    logger.debug('cache_get key=%s', key)

    # caches should be sorted from fastest to slowest, ie, [SimpleMemoryCache,
    # RedisCache]
    for cache in caches:
        cached_response = await cache.get(key)
        if cached_response:
            logger.debug('cache_get response %s: %s', cache, cached_response)
            return merge_cached_response(cached_response,
                                         single_jsonrpc_request)
    logger.debug('cache_get miss with key=%s', key)


@ignore_errors_async
async def cache_set(sanic_http_request: HTTPRequest,
                    single_jsonrpc_request: SingleJsonRpcRequest,
                    value: Union[AnyStr, dict],
                    ttl=None,
                    **kwargs):
    last_irreversible_block_num = sanic_http_request.app.config.last_irreversible_block_num
    ttl = ttl or ttl_from_jsonrpc_request(single_jsonrpc_request,
                                          last_irreversible_block_num, value)
    if ttl == TTL.NO_CACHE:
        logger.debug('skipping cache for ttl=%s value %s', ttl, value)
        return
    if isinstance(ttl, TTL):
        ttl = ttl.value
    caches = sanic_http_request.app.config.caches
    key = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    futures = []
    for cache in caches:
        logger.debug('%s.set(%s, %s, ttl=%s)', cache, key, value, ttl)
        futures.append(asyncio.ensure_future(
            cache.set(key, value, ttl=ttl, **kwargs)))
    await asyncio.wait(futures, timeout=5)


async def cache_get_batch(caches: Caches,
                          jsonrpc_batch_request: BatchJsonRpcRequest
                          ) -> BatchJsonRpcResponse:
    keys = list(map(jsonrpc_cache_key, jsonrpc_batch_request))
    key_count = len(keys)
    logger.debug(f'cache_get_batch keys:{keys}')
    batch_responses = [None for req in jsonrpc_batch_request]
    for cache in caches:
        missing = [key for key, response in zip(
            keys, batch_responses) if not response]
        cached_responses = await cache.multi_get(missing)
        cached_iter = iter(cached_responses)
        logger.debug(
            f'{cache} hits: {len([r for r in cached_responses if r])}/{len(missing)}')
        batch_responses = [existing or next(
            cached_iter) for existing in batch_responses]
        if all(batch_responses):
            break
    logger.debug(
        f'cache_get_batch final hits: {len([r for r in batch_responses if r])}/{key_count}')
    return merge_cached_responses(jsonrpc_batch_request, batch_responses)


async def cache_jsonrpc_response(
        sanic_http_request: HTTPRequest,
        single_jsonrpc_request: SingleJsonRpcRequest,
        jsonrpc_response: SingleJsonRpcResponse) -> None:
    """Don't cache error responses
    """
    if is_jsonrpc_error_response(jsonrpc_response):
        logger.warning(
            'jsonrpc error in response from upstream %s, skipping cache',
            jsonrpc_response)
        return
    # if 'id' in jsonrpc_response:
    #    del jsonrpc_response['id']
    asyncio.ensure_future(
        cache_set(sanic_http_request, single_jsonrpc_request,
                  jsonrpc_response))


def ttl_from_jsonrpc_request(single_jsonrpc_request: SingleJsonRpcRequest,
                             last_irreversible_block_num: int=0,
                             jsonrpc_response: dict=None) -> TTL:
    urn = jsonrpc_cache_key(single_jsonrpc_request=single_jsonrpc_request)
    ttl = ttl_from_urn(urn)
    if ttl == TTL.NO_EXPIRE_IF_IRREVERSIBLE:
        ttl = irreversible_ttl(jsonrpc_response, last_irreversible_block_num)
    return ttl


def ttl_from_urn(urn: str) -> TTL:
    _, ttl = jussi.jsonrpc_method_cache_settings.TTLS.longest_prefix(urn)
    logger.debug(f'ttl from urn:{urn} ttl:{ttl}')
    return ttl


def irreversible_ttl(jsonrpc_response: dict=None,
                     last_irreversible_block_num: int=0) -> TTL:
    if not jsonrpc_response:
        logger.debug(
            'unable to extract block num from jsonrpc response, skipping cache')
        return TTL.NO_CACHE
    if not last_irreversible_block_num:
        logger.debug('missing last_irrersible_block_num, skipping cache')
        return TTL.NO_CACHE
    try:
        jrpc_block_num = block_num_from_jsonrpc_response(jsonrpc_response)
        if last_irreversible_block_num < jrpc_block_num:
            logger.debug('skipping cache for block_num > last_irreversible')
            return TTL.NO_CACHE
        return TTL.NO_EXPIRE
    except Exception as e:
        logger.info('Unable to cache using last irreversible block: %s', e)
        return TTL.NO_CACHE


def block_num_from_jsonrpc_response(
        jsonrpc_response: SingleJsonRpcRequest=None) -> int:
    # pylint: disable=no-member
    # for get_block
    block_id = cytoolz.get_in(['result', 'block_id'], jsonrpc_response)
    if block_id:
        return block_num_from_id(block_id)

    # for get_block_header
    previous = cytoolz.get_in(['result', 'previous'], jsonrpc_response)
    return block_num_from_id(previous) + 1


def block_num_from_id(block_hash: str) -> int:
    """return the first 4 bytes (8 hex digits) of the block ID (the block_num)
    """
    return int(str(block_hash)[:8], base=16)


def merge_cached_response(
        cached_response: CachedSingleResponse,
        jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcRequest:
    logger.debug(
        f'merge_cached_response merging response into {type(cached_response)}({cached_response})')
    if 'id' in cached_response:
        del cached_response['id']
    if 'id' in jsonrpc_request:
        cached_response['id'] = jsonrpc_request['id']
    return cached_response


def merge_cached_responses(
        jsonrpc_batch_request: BatchJsonRpcRequest,
        cached_responses: CachedBatchResponse) -> CachedBatchResponse:
    merged = []
    for cached, request, in zip(cached_responses, jsonrpc_batch_request):
        if cached:
            merged.append(merge_cached_response(cached, request))
        else:
            merged.append(None)
    return merged
