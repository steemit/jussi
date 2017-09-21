# -*- coding: utf-8 -*-
import asyncio
import logging
from typing import Optional

import cytoolz
from aiocache import SimpleMemoryCache

from jussi.validators import is_get_block_request
from jussi.validators import is_valid_get_block_response

from ..typedefs import BatchJsonRpcRequest
from ..typedefs import BatchJsonRpcResponse
from ..typedefs import JsonRpcRequest
from ..typedefs import JsonRpcResponse
from ..typedefs import SingleJsonRpcRequest
from ..typedefs import SingleJsonRpcResponse
from ..upstream import is_batch_jsonrpc
from ..upstream import is_jsonrpc_error_response
from ..validators import is_valid_non_error_jsonrpc_response
from .jsonrpc_method_cache_settings import TTL
from .utils import jsonrpc_cache_key
from .utils import merge_cached_response
from .utils import merge_cached_responses
from .utils import ttl_from_jsonrpc_request

logger = logging.getLogger(__name__)


class UncacheableResponse(Exception):
    pass


class CacheGroup(object):
    # pylint: disable=unused-argument, too-many-arguments, no-else-return
    def __init__(self, caches):
        self._fast_caches = []
        self._slow_caches = []
        self._caches = []

        for cache in caches:
            if isinstance(cache, SimpleMemoryCache):
                self._fast_caches.append(cache)
            else:
                self._slow_caches.append(cache)

        self._caches.extend(self._fast_caches)
        self._caches.extend(self._slow_caches)

        logger.info('CacheGroup configured using %s', self._caches)

    async def set(self, key, value, **kwargs):
        return await asyncio.gather(*[asyncio.ensure_future(cache.set(key, value, **kwargs)) for cache in self._caches])

    async def get(self, key, **kwargs):
        for cache in self._caches:
            result = await cache.get(key, **kwargs)
            if result is not None:
                return result

    async def multi_get(self, keys, **kwargs):
        results = [None for key in keys]
        for cache in self._caches:
            missing = [
                key for key, response in zip(
                    keys, results) if not response]
            cache_results = await cache.multi_get(missing, **kwargs)
            cache_iter = iter(cache_results)
            results = [existing or next(cache_iter) for existing in results]
            if all(results):
                return results
        return results

    async def multi_set(self, triplets):
        # pylint: disable=no-member
        grouped_by_ttl = cytoolz.groupby(lambda t: t[2], triplets)
        futures = []
        for cache in self._caches:
            for ttl, ttl_group in grouped_by_ttl.items():
                pairs = [t[:2] for t in ttl_group]
                futures.append(
                    asyncio.ensure_future(
                        cache.multi_set(
                            pairs, ttl=ttl)))
        return await asyncio.gather(*futures)

    async def clear(self):
        return await asyncio.gather(*[cache.clear() for cache in self._caches])

    async def close(self):
        return await asyncio.gather(*[cache.close() for cache in self._caches])

    # jsonrpc related methods
    #

    async def cache_jsonrpc_response(self,
                                     request: JsonRpcRequest,
                                     response: JsonRpcResponse) -> None:
        """Don't cache error responses
        """
        try:
            if is_batch_jsonrpc(request):
                return await self.cache_batch_jsonrpc_response(request,
                                                               response)
            else:
                return await self.cache_single_jsonrpc_response(request,
                                                                response)
        except UncacheableResponse as e:
            logger.warning(e)

    async def get_jsonrpc_response(self,
                                   request: JsonRpcRequest) -> Optional[JsonRpcResponse]:
        if is_batch_jsonrpc(request):
            return await self.get_batch_jsonrpc_responses(request)
        else:
            return await self.get_single_jsonrpc_response(request)

    async def get_single_jsonrpc_response(self,
                                          request: JsonRpcRequest)-> Optional[SingleJsonRpcResponse]:
        key = jsonrpc_cache_key(request)
        cached_response = await self.get(key)
        if cached_response:
            return merge_cached_response(request, cached_response)
        return

    async def get_batch_jsonrpc_responses(self,
                                          requests: BatchJsonRpcRequest) ->Optional[BatchJsonRpcResponse]:
        keys = [jsonrpc_cache_key(request) for request in requests]
        cached_responses = await self.multi_get(keys)
        return merge_cached_responses(requests, cached_responses)

    async def cache_single_jsonrpc_response(self,
                                            request: SingleJsonRpcRequest,
                                            response: SingleJsonRpcResponse,
                                            key: str = None,
                                            ttl: str = None
                                            ) -> None:

        last_irreversible_block_num = 15_000_000  # FIXME
        value = await self.prepare_response_for_cache(request, response)
        key = key or jsonrpc_cache_key(request)
        ttl = ttl or ttl_from_jsonrpc_request(request,
                                              last_irreversible_block_num, value)
        if ttl == TTL.NO_CACHE:
            logger.debug('skipping cache for ttl=%s value %s', ttl, value)
            return
        if isinstance(ttl, TTL):
            ttl = ttl.value
        return await self.set(key, value, ttl=ttl)

    async def cache_batch_jsonrpc_response(self,
                                           requests: BatchJsonRpcRequest,
                                           responses: BatchJsonRpcResponse) -> None:
        last_irreversible_block_num = 15_000_000  # FIXME
        triplets = []

        for i, response in enumerate(responses):
            value = await self.prepare_response_for_cache(requests[i],
                                                          response)
            key = jsonrpc_cache_key(requests[i])
            ttl = ttl_from_jsonrpc_request(requests[i],
                                           last_irreversible_block_num, value)
            if ttl == TTL.NO_CACHE:
                continue
            if isinstance(ttl, TTL):
                ttl = ttl.value
            triplets.append((key, value, ttl))
        await self.multi_set(triplets)

    async def prepare_response_for_cache(self,
                                         request: SingleJsonRpcRequest,
                                         response: SingleJsonRpcResponse) -> Optional[SingleJsonRpcRequest]:
        if is_jsonrpc_error_response(response):
            logger.warning(
                'jsonrpc error in response from upstream %s, skipping cache',
                response)
            raise UncacheableResponse('jsonrpc error response')
        if is_get_block_request(jsonrpc_request=request):
            if not is_valid_get_block_response(jsonrpc_request=request,
                                               response=response):
                logger.warning('invalid get_block response, skipping cache')
                raise UncacheableResponse('invalid get_block response')
        if 'id' in response:
            del response['id']
        return response

    # pylint: disable=no-self-use
    def is_complete_response(self, request: JsonRpcRequest,
                             cached_response: JsonRpcResponse) -> bool:
        if not is_valid_non_error_jsonrpc_response(cached_response):
            return False
        if isinstance(request, list):
            return len(request) == len(cached_response)
        return True

    def x_jussi_cache_key(self, request: JsonRpcRequest) -> str:
        if isinstance(request, dict):
            return jsonrpc_cache_key(request)
        else:
            return 'batch'
