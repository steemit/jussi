# -*- coding: utf-8 -*-
import asyncio
from typing import Any
from typing import List
from typing import Tuple
from typing import TypeVar
from typing import NoReturn
from typing import Optional

import structlog

from jussi.errors import JussiInteralError
from jussi.validators import is_get_block_request
from jussi.validators import is_valid_get_block_response

from .ttl import TTL
from .utils import irreversible_ttl
from .utils import jsonrpc_cache_key
from .utils import merge_cached_response
from .utils import merge_cached_responses
from ..typedefs import JrpcRequest
from ..typedefs import JrpcResponse
from ..typedefs import BatchJrpcRequest
from ..typedefs import BatchJrpcResponse
from ..typedefs import SingleJrpcRequest
from ..typedefs import SingleJrpcResponse
from ..validators import is_valid_non_error_jussi_response
from ..validators import is_valid_non_error_single_jsonrpc_response
from .backends.max_ttl import SimplerMaxTTLMemoryCache

logger = structlog.getLogger(__name__)

CacheTTL = Optional[int]
CacheKey = str
CacheKeys = List[CacheKey]
CacheValue = TypeVar('CacheValue', int, float, str, dict)
CachePair = Tuple[CacheKey, CacheValue]
CacheTriplet = Tuple[CacheKey, CacheValue, CacheTTL]
CacheTriplets = List[CacheTriplet]
CacheResultValue = TypeVar('CacheValue', int, float, str, dict)
CacheResult = Optional[CacheResultValue]
CacheResults = List[CacheResult]


class UncacheableResponse(JussiInteralError):
    message = 'Uncacheable response'


SLOW_TIER = 1
FAST_TIER = 2


class CacheGroup:
    # pylint: disable=unused-argument, too-many-arguments, no-else-return
    def __init__(self, caches: List[Any]) -> None:
        self._cache_group_items = caches
        self._memory_cache = SimplerMaxTTLMemoryCache()
        self._read_cache_items = []
        self._read_caches = []
        self._write_cache_items = []
        self._write_caches = []
        self._all_caches = [cache_item.cache for cache_item in self._cache_group_items]

        self._read_cache_items = list(
            sorted(
                filter(
                    lambda i: i.read,
                    self._cache_group_items),
                key=lambda i: i.speed_tier,
                reverse=True))
        self._read_caches = [item.cache for item in self._read_cache_items]

        self._write_cache_items = list(
            sorted(
                filter(
                    lambda i: i.write,
                    self._cache_group_items),
                key=lambda i: i.speed_tier,
                reverse=True))
        self._write_caches = [item.cache for item in self._write_cache_items]

        if self._read_caches == [] and len(self._write_caches) > 0:
            logger.info('setting single write cache as read/write')
            self._read_caches = self._write_caches

        logger.info('CacheGroup configured',
                    items=self._cache_group_items,
                    read_items=self._read_cache_items,
                    write_items=self._write_cache_items,
                    read_caches=self._read_caches,
                    write_caches=self._write_caches)

    async def get(self, key: CacheKey) -> CacheResult:
        # no memory cache read here for optimization, it has already happened
        for cache in self._read_caches:
            result = await cache.get(key)
            if result is not None:
                return result

    async def multi_get(self, keys: CacheKeys) -> CacheResults:
        # set blank results object
        results = [None for key in keys]

        # check memory cache first, preserving cache hits if not all hits
        memory_cache_results = self._memory_cache.multi_gets(keys)
        cache_iter = iter(memory_cache_results)
        results = [existing or next(cache_iter) for existing in results]
        if all(results):
            return results

        # read from one cache at a time
        for cache in self._read_caches:
            missing = [
                key for key, response in zip(
                    keys, results) if not response]
            cache_results = await cache.multi_get(missing)
            cache_iter = iter(cache_results)
            results = [existing or next(cache_iter) for existing in results]
            if all(results):
                return results
        return results

    async def set(self, key: CacheKey, value: CacheValue, expire_time: CacheTTL=None) -> NoReturn:
        self._memory_cache.sets(key, value, expire_time=expire_time)
        await asyncio.gather(*[cache.set(key, value, expire_time=expire_time) for cache
                               in self._write_caches], return_exceptions=False)

    async def multi_set(self, triplets: CacheTriplets) -> NoReturn:
        # pylint: disable=no-member
        # set memory cache
        self._memory_cache.multi_sets(triplets)

        # FIXME with pipeline
        futures = []
        ttl = triplets[0][2]
        pairs = {k: v for k, v, t in triplets}
        for cache in self._write_caches:
            futures.extend([cache.set_many(pairs, expire_time=ttl)])
        if futures:
            await asyncio.gather(*futures, return_exceptions=False)

    async def clear(self) -> NoReturn:
        self._memory_cache.clears()
        await asyncio.gather(*[cache.clear() for cache in self._write_caches])

    async def close(self) -> NoReturn:
        for cache in self._all_caches:
            cache.client.connection_pool.disconnect()

    # jsonrpc related methods
    #

    async def cache_jsonrpc_response(self,
                                     request: JrpcRequest = None,
                                     response: JrpcResponse = None,
                                     last_irreversible_block_num: int = None) -> NoReturn:
        """Don't cache error responses
        """
        try:
            if isinstance(request, list):
                await self.cache_batch_jsonrpc_response(requests=request,
                                                        responses=response,
                                                        last_irreversible_block_num=last_irreversible_block_num)
            else:
                await self.cache_single_jsonrpc_response(request=request,
                                                         response=response,
                                                         last_irreversible_block_num=last_irreversible_block_num)
        except UncacheableResponse:
            pass
        except Exception as e:
            logger.error('error while caching response', e=e)

    async def get_jsonrpc_response(self,
                                   request: JrpcRequest) -> Optional[JrpcResponse]:
        if not isinstance(request, list):
            return await self.get_single_jsonrpc_response(request)
        else:
            return await self.get_batch_jsonrpc_responses(request)

    async def get_single_jsonrpc_response(self,
                                          request: SingleJrpcRequest) -> Optional[SingleJrpcResponse]:
        if request.upstream.ttl == TTL.NO_CACHE:
            return None
        key = jsonrpc_cache_key(request)
        cached_response = self._memory_cache.gets(key)
        if cached_response is not None:
            return merge_cached_response(request, cached_response)
        cached_response = await self.get(key)
        if cached_response is not None:
            return merge_cached_response(request, cached_response)
        return None

    async def get_batch_jsonrpc_responses(self,
                                          requests: BatchJrpcRequest) -> \
            Optional[BatchJrpcResponse]:
        keys = [jsonrpc_cache_key(request) for request in requests]
        cached_responses = await self.multi_get(keys)
        return merge_cached_responses(requests, cached_responses)

    async def cache_single_jsonrpc_response(self,
                                            request: SingleJrpcRequest = None,
                                            response: SingleJrpcResponse = None,
                                            ttl: str = None,
                                            last_irreversible_block_num: int = None
                                            ) -> None:
        key = jsonrpc_cache_key(request)
        ttl = ttl or request.upstream.ttl
        if ttl == TTL.NO_EXPIRE_IF_IRREVERSIBLE:
            last_irreversible_block_num = last_irreversible_block_num or \
                await self.get('last_irreversible_block_num')
            ttl = irreversible_ttl(jsonrpc_response=response,
                                   last_irreversible_block_num=last_irreversible_block_num)
        elif ttl == TTL.NO_CACHE:
            return
        if isinstance(ttl, TTL):
            ttl = ttl.value
        value = self.prepare_response_for_cache(request, response)
        await self.set(key, value, expire_time=ttl)

    async def cache_batch_jsonrpc_response(self,
                                           requests: BatchJrpcRequest = None,
                                           responses: BatchJrpcResponse = None,
                                           last_irreversible_block_num: int = None) -> None:
        triplets = []
        ttls = set(r.upstream.ttl for r in requests)
        if TTL.NO_EXPIRE_IF_IRREVERSIBLE in ttls:
            last_irreversible_block_num = last_irreversible_block_num or \
                await self.get(
                    'last_irreversible_block_num')
        for i, response in enumerate(responses):
            key = jsonrpc_cache_key(requests[i])
            ttl = requests[i].upstream.ttl
            if ttl == TTL.NO_EXPIRE_IF_IRREVERSIBLE:
                ttl = irreversible_ttl(response,
                                       last_irreversible_block_num)
            elif ttl == TTL.NO_CACHE:
                continue
            if isinstance(ttl, TTL):
                ttl = ttl.value
            value = self.prepare_response_for_cache(requests[i],
                                                    response)
            triplets.append((key, value, ttl))
            await self.multi_set(triplets)

    # pylint: disable=no-self-use
    def prepare_response_for_cache(self,
                                   request: SingleJrpcRequest,
                                   response: SingleJrpcResponse) -> \
            Optional[SingleJrpcResponse]:
        if not is_valid_non_error_single_jsonrpc_response(response):
            raise UncacheableResponse(reason='is_valid_non_error_single_jsonrpc_response',
                                      jrpc_request=request,
                                      jrpc_response=response)

        if is_get_block_request(request=request):
            if not is_valid_get_block_response(request=request,
                                               response=response):
                raise UncacheableResponse(reason='invalid get_block response',
                                          jrpc_request=request,
                                          jrpc_response=response)
        return response
    # pylint: enable=no-self-use

    @staticmethod
    def is_complete_response(request: JrpcRequest,
                             cached_response: JrpcResponse) -> bool:
        return is_valid_non_error_jussi_response(request, cached_response)

    @staticmethod
    def x_jussi_cache_key(request: JrpcRequest) -> str:
        if isinstance(request, SingleJrpcRequest):
            return jsonrpc_cache_key(request)
        else:
            return 'batch'
