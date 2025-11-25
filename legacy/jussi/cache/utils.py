# -*- coding: utf-8 -*-
import functools
from typing import Optional

import cytoolz
import structlog

from ..typedefs import BatchJrpcRequest
from ..typedefs import CachedBatchResponse
from ..typedefs import CachedSingleResponse
from ..typedefs import SingleJrpcRequest
from ..typedefs import SingleJrpcResponse
from .ttl import TTL

logger = structlog.get_logger(__name__)


@functools.lru_cache(8192)
def jsonrpc_cache_key(single_jsonrpc_request: SingleJrpcRequest) -> str:
    return str(single_jsonrpc_request.urn)


def irreversible_ttl(jsonrpc_response: dict=None,
                     last_irreversible_block_num: int=None) -> TTL:
    if not jsonrpc_response:
        return TTL.NO_CACHE
    if not isinstance(last_irreversible_block_num, int):
        logger.debug('bad/missing last_irrersible_block_num',
                     lirb=last_irreversible_block_num)
        return TTL.NO_CACHE
    try:
        jrpc_block_num = block_num_from_jsonrpc_response(jsonrpc_response)
        return TTL.DEFAULT_TTL
    except Exception as e:
        logger.warning(
            'Unable to cache using last irreversible block',
            e=e,
            lirb=last_irreversible_block_num)
    return TTL.NO_CACHE


def block_num_from_jsonrpc_response(
        jsonrpc_response: dict=None) -> Optional[int]:
    # pylint: disable=no-member
    get_in = cytoolz.get_in
    # for appbase get_block
    block_id = get_in(['result', 'block', 'block_id'], jsonrpc_response)
    if block_id:
        return int(str(block_id)[:8], base=16)

    # for appbase get_block_header
    previous = get_in(['result', 'header', 'previous'],
                      jsonrpc_response)
    if previous:
        return int(str(previous)[:8], base=16) + 1

    # for steemd get_block
    block_id = get_in(['result', 'block_id'], jsonrpc_response)
    if block_id:
        return int(str(block_id)[:8], base=16)

    # for steemd get_block_header
    previous = get_in(['result', 'previous'],
                      jsonrpc_response)
    if previous:
        return int(str(previous)[:8], base=16) + 1
    return None


def merge_cached_response(request: SingleJrpcRequest,
                          cached_response: CachedSingleResponse,
                          ) -> Optional[SingleJrpcResponse]:
    if not cached_response:
        return None
    return {'id': request.id, 'jsonrpc': '2.0', 'result': cached_response['result']}


def merge_cached_responses(request: BatchJrpcRequest,
                           cached_responses: CachedBatchResponse) -> CachedBatchResponse:
    return [merge_cached_response(req, resp) for req, resp in zip(
        request, cached_responses)]
