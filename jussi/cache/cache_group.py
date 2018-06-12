# -*- coding: utf-8 -*-
import asyncio
from typing import Optional
from typing import Any
from typing import List
from typing import Union
from typing import NoReturn


import cytoolz
import structlog

from jussi.errors import JussiInteralError
from jussi.validators import is_get_block_request
from jussi.validators import is_valid_get_block_response

from ..typedefs import BatchJsonRpcRequest
from ..typedefs import BatchJsonRpcResponse
from ..typedefs import JsonRpcRequest
from ..typedefs import JsonRpcResponse
from ..typedefs import JsonRpcResponseDict
from ..typedefs import SingleJsonRpcRequest
from ..typedefs import SingleJsonRpcResponse
from ..validators import is_valid_jussi_response
from ..validators import is_valid_non_error_single_jsonrpc_response
from .ttl import TTL
from .utils import irreversible_ttl
from .utils import jsonrpc_cache_key
from .utils import merge_cached_response
from .utils import merge_cached_responses

logger = structlog.getLogger(__name__)


class UncacheableResponse(JussiInteralError):
    message = 'Uncacheable response'


SLOW_TIER = 1
FAST_TIER = 2


class CacheGroup(object):
    # pylint: disable=unused-argument, too-many-arguments, no-else-return
    def __init__(self, caches: List[Any]) -> None:
        self._cache_group_items = caches
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

        logger.info('CacheGroup configured',
                    items=self._cache_group_items,
                    read_items=self._read_cache_items,
                    write_items=self._write_cache_items,
                    read_caches=self._read_caches,
                    write_caches=self._write_caches)

    async def set(self, key: str, value: Any, **kwargs) -> NoReturn:
        await asyncio.gather(*[cache.set(key, value, **kwargs) for cache
                               in self._write_caches], return_exceptions=False)

    async def get(self, key: str, **kwargs) -> Union[asyncio.Future, None]:
        for cache in self._read_caches:
            result = await cache.get(key, **kwargs)
            if result is not None:
                return result

    async def multi_get(self, keys, **kwargs):
        results = [None for key in keys]
        for cache in self._read_caches:
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
        for cache in self._write_caches:
            for ttl, ttl_group in grouped_by_ttl.items():
                pairs = [t[:2] for t in ttl_group]
                futures.append(
                    cache.multi_set(
                        pairs, ttl=ttl))
        await asyncio.gather(*futures, return_exceptions=False)

    async def clear(self) -> Union[asyncio.tasks._GatheringFuture, List[bool]]:
        return await asyncio.gather(*[cache.clear() for cache in self._write_caches])

    async def close(self) -> Union[asyncio.tasks._GatheringFuture, List[None]]:
        return await asyncio.gather(*[cache.close() for cache in self._all_caches])

    # jsonrpc related methods
    #

    async def cache_jsonrpc_response(self,
                                     request: JsonRpcRequest = None,
                                     response: JsonRpcResponse = None,
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
                                   request: JsonRpcRequest) -> Optional[
            JsonRpcResponse]:
        if isinstance(request, list):
            return await self.get_batch_jsonrpc_responses(request)
        else:
            return await self.get_single_jsonrpc_response(request)

    async def get_single_jsonrpc_response(self,
                                          request: JsonRpcRequest) -> Optional[
            SingleJsonRpcResponse]:
        if request.upstream.ttl == TTL.NO_CACHE:
            return None
        key = jsonrpc_cache_key(request)
        cached_response = await self.get(key)
        if cached_response is None:
            return None
        return merge_cached_response(request, cached_response)

    async def get_batch_jsonrpc_responses(self,
                                          requests: BatchJsonRpcRequest) -> \
            Optional[BatchJsonRpcResponse]:
        keys = [jsonrpc_cache_key(request) for request in requests]
        cached_responses = await self.multi_get(keys)

        return merge_cached_responses(requests, cached_responses)

    async def cache_single_jsonrpc_response(self,
                                            request: SingleJsonRpcRequest = None,
                                            response: SingleJsonRpcResponse = None,
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
            logger.debug('skipping cache', ttl=ttl, urn=request.urn)
            return
        if isinstance(ttl, TTL):
            ttl = ttl.value
        value = await self.prepare_response_for_cache(request, response)
        await self.set(key, value, ttl=ttl)

    async def cache_batch_jsonrpc_response(self,
                                           requests: BatchJsonRpcRequest = None,
                                           responses: BatchJsonRpcResponse = None,
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
            value = await self.prepare_response_for_cache(requests[i],
                                                          response)
            triplets.append((key, value, ttl))
            await self.multi_set(triplets)

    async def prepare_response_for_cache(self,
                                         request: SingleJsonRpcRequest,
                                         response: SingleJsonRpcResponse) -> \
            Optional[JsonRpcResponseDict]:
        if not is_valid_non_error_single_jsonrpc_response(response):
            raise UncacheableResponse(reason='is_valid_non_error_single_jsonrpc_response',
                                      jrpc_request=request,
                                      jrpc_response=response)

        if is_get_block_request(jsonrpc_request=request):
            if not is_valid_get_block_response(jsonrpc_request=request,
                                               response=response):
                raise UncacheableResponse(reason='invalid get_block response',
                                          jrpc_request=request,
                                          jrpc_response=response)
        return response

    @staticmethod
    def is_complete_response(request: JsonRpcRequest,
                             cached_response: JsonRpcResponse) -> bool:
        return is_valid_jussi_response(request, cached_response)

    @staticmethod
    def x_jussi_cache_key(request: JsonRpcRequest) -> str:
        if isinstance(request, SingleJsonRpcRequest):
            return jsonrpc_cache_key(request)
        else:
            return 'batch'
