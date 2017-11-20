# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging
import random
import time

from typing import Optional

import async_timeout
from sanic import response

import ujson

from .errors import UpstreamResponseError
from .typedefs import BatchJsonRpcRequest
from .typedefs import BatchJsonRpcResponse
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcRequest
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream.url import url_from_jsonrpc_request
from .upstream.urn import urn_parts as get_urn_parts
from .utils import async_retry
from .utils import is_batch_jsonrpc
from .utils import update_last_irreversible_block_num

logger = logging.getLogger(__name__)
debug_logger = logging.getLogger('jussi_debug')
request_logger = logging.getLogger('jussi_request')


# path /
async def handle_jsonrpc(sanic_http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json  # type: JsonRpcRequest

    # make upstream requests
    if is_batch_jsonrpc(sanic_http_request=sanic_http_request):
        jsonrpc_response = await dispatch_batch(sanic_http_request,
                                                jsonrpc_requests)
    else:
        jsonrpc_response = await dispatch_single(sanic_http_request,
                                                 jsonrpc_requests)
    return response.json(jsonrpc_response)


async def healthcheck(sanic_http_request: HTTPRequest) -> HTTPResponse:
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat(),
        'source_commit': sanic_http_request.app.config.args.source_commit,
        'docker_tag': sanic_http_request.app.config.args.docker_tag
    })


# pylint: disable=no-value-for-parameter, too-many-locals
@async_retry(tries=3)
@update_last_irreversible_block_num
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest,
                   url: str,
                   batch_index: int) -> SingleJsonRpcResponse:
    pools = sanic_http_request.app.config.websocket_pools
    pool = pools[url]
    jussi_request_id = sanic_http_request.headers.get('x-jussi-request-id')

    upstream_request = {k: jsonrpc_request[k] for k in
                        {'jsonrpc', 'method', 'params'} if k in jsonrpc_request}
    upstream_request['id'] = sanic_http_request['request_id_int'] + batch_index

    urn_parts = get_urn_parts(upstream_request)
    timeout = sanic_http_request.app.config.timeout_from_request(upstream_request)
    conn = await pool.acquire()
    start = time.perf_counter()
    request_info = dict(jussi_request_id=jussi_request_id,
                        jsonrpc_request_id=jsonrpc_request.get('id'),
                        upstream_request_id=upstream_request['id'],
                        batch_index=batch_index,
                        conn_id=id(conn),
                        time_to_upstream=start - sanic_http_request['timing'],
                        url=url,
                        namespace=urn_parts.namespace,
                        api=urn_parts.api,
                        method=urn_parts.method,
                        params=urn_parts.params,
                        timeout=timeout)

    with async_timeout.timeout(timeout):
        elapsed = -1
        try:
            upstream_request_json = ujson.dumps(upstream_request, ensure_ascii=False).encode()

            await conn.send(upstream_request_json)
            upstream_response_json = await conn.recv()
            elapsed = time.perf_counter() - start
            request_info.update(elapsed=elapsed)
            request_logger.info(request_info)
            upstream_response = ujson.loads(upstream_response_json)
            debug_logger.debug(dict(jussi_request_id=jussi_request_id,
                                    jsonrpc_request_id=jsonrpc_request.get('id'),
                                    upstream_request_id=upstream_request['id'],
                                    url=url,
                                    upstream_request=upstream_request,
                                    upstream_response=upstream_response))

            assert int(upstream_response.get('id')) == upstream_request['id'], \
                f'{upstream_response.get("id")} should be {upstream_request["id"]}'

            del upstream_response['id']
            if 'id' in jsonrpc_request:
                upstream_response['id'] = jsonrpc_request['id']
            return upstream_response

        except AssertionError as e:
            request_info.update(upstream_request=upstream_request)
            try:
                request_info['upstream_response'] = upstream_response
            except NameError:
                pass
            logger.error(request_info)
            await pool.terminate_connection(conn)
            raise UpstreamResponseError(sanic_request=sanic_http_request,
                                        exception=e)
        except Exception as e:
            logger.exception(f'fetch_ws failed')
            await pool.terminate_connection(conn)
            raise e
        finally:
            await pool.release(conn)


@async_retry(tries=3)
@update_last_irreversible_block_num
async def fetch_http(sanic_http_request: HTTPRequest,
                     jsonrpc_request: SingleJsonRpcRequest,
                     url: str,
                     batch_index: int) -> SingleJsonRpcResponse:

    session = sanic_http_request.app.config.aiohttp['session']
    args = sanic_http_request.app.config.args
    headers = {}
    headers['x-amzn-trace_id'] = sanic_http_request.headers.get('x-amzn-trace-id')
    headers['x-jussi-request-id'] = sanic_http_request.headers.get('x-jussi-request-id')

    upstream_request = {k: jsonrpc_request[k] for k in
                        {'jsonrpc', 'method', 'params'} if k in jsonrpc_request}
    upstream_request['id'] = sanic_http_request['request_id_int'] + batch_index

    with async_timeout.timeout(args.upstream_http_timeout):
        async with session.post(url, json=upstream_request, headers=headers) as resp:
            upstream_response = await resp.json()

        del upstream_response['id']
        if 'id' in jsonrpc_request:
            upstream_response['id'] = jsonrpc_request['id']
        return upstream_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest,
                          batch_index: int=None) -> SingleJsonRpcResponse:

    url = url_from_jsonrpc_request(
        sanic_http_request.app.config.upstream_urls, jsonrpc_request)
    if batch_index is None:
        batch_index = 0

    # pylint: disable=unexpected-keyword-arg
    if url.startswith('ws'):
        json_response = await fetch_ws(
            sanic_http_request,
            jsonrpc_request,
            url,
            batch_index)
    else:
        json_response = await fetch_http(
            sanic_http_request,
            jsonrpc_request,
            url,
            batch_index)
    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: BatchJsonRpcRequest
                         ) -> BatchJsonRpcResponse:
    requests = [dispatch_single(sanic_http_request, request, i)
                for i, request in enumerate(jsonrpc_requests)]
    return await asyncio.gather(*requests)
