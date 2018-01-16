# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging
import time

import async_timeout
from sanic import response

import ujson

from .errors import UpstreamResponseError
from .typedefs import BatchJsonRpcRequest
from .typedefs import BatchJsonRpcResponse
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .utils import is_batch_jsonrpc

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
async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest,
                   batch_index: int) -> SingleJsonRpcResponse:
    pools = sanic_http_request.app.config.websocket_pools
    pool = pools[jsonrpc_request.upstream.url]
    jussi_request_id = sanic_http_request.headers.get('x-jussi-request-id')

    upstream_id = sanic_http_request['request_id_int'] + batch_index
    upstream_request_json = jsonrpc_request.to_upstream_request(upstream_id)
    conn = await pool.acquire()
    start = time.perf_counter()

    with async_timeout.timeout(jsonrpc_request.upstream.timeout):
        elapsed = -1
        try:
            await conn.send(upstream_request_json)
            upstream_response_json = await conn.recv()
            elapsed = time.perf_counter() - start
            upstream_response = ujson.loads(upstream_response_json)
            assert int(upstream_response.get('id')) == upstream_id, \
                f'{upstream_response.get("id")} should be {upstream_id}'
            del upstream_response['id']
            if jsonrpc_request.id is not False:
                upstream_response['id'] = jsonrpc_request.id
            return upstream_response

        except AssertionError as e:
            request_info = dict(jussi_request_id=jussi_request_id,
                                jsonrpc_request_id=jsonrpc_request.id,
                                upstream_request_id=upstream_id,
                                batch_index=batch_index,
                                conn_id=id(conn),
                                time_to_upstream=start - sanic_http_request['timing'],
                                url=jsonrpc_request.upstream.url,
                                namespace=jsonrpc_request.urn.namespace,
                                api=jsonrpc_request.urn.api,
                                method=jsonrpc_request.urn.method,
                                params=jsonrpc_request.urn.params,
                                timeout=jsonrpc_request.upstream.timeout,
                                elapsed=elapsed,
                                upstream_request=upstream_request_json,
                                upstream_response=upstream_response)
            request_info.update(upstream_request=upstream_request_json)
            try:
                request_info['upstream_response'] = upstream_response
            except NameError:
                pass
            logger.exception(request_info)
            await pool.terminate_connection(conn)
            raise UpstreamResponseError(sanic_request=sanic_http_request,
                                        exception=e)
        except Exception as e:
            logger.exception(f'fetch_ws failed')
            await pool.terminate_connection(conn)
            raise e
        finally:
            await pool.release(conn)


async def fetch_http(sanic_http_request: HTTPRequest,
                     jsonrpc_request: SingleJsonRpcRequest,
                     batch_index: int) -> SingleJsonRpcResponse:

    session = sanic_http_request.app.config.aiohttp['session']
    headers = {}
    headers['x-amzn-trace_id'] = sanic_http_request.headers.get('x-amzn-trace-id', 'none')
    headers['x-jussi-request-id'] = sanic_http_request.headers.get('x-jussi-request-id', 'none')

    upstream_id = sanic_http_request['request_id_int'] + batch_index
    upstream_request = jsonrpc_request.to_upstream_request(upstream_id, as_json=False)

    with async_timeout.timeout(jsonrpc_request.upstream.timeout):
        async with session.post(jsonrpc_request.upstream.url,
                                json=upstream_request) as resp:
            upstream_response = await resp.json()

        del upstream_response['id']
        if 'id' in jsonrpc_request:
            upstream_response['id'] = jsonrpc_request.id
        return upstream_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest,
                          batch_index: int=None) -> SingleJsonRpcResponse:

    if batch_index is None:
        batch_index = 0

    # pylint: disable=unexpected-keyword-arg
    if jsonrpc_request.upstream.url.startswith('ws'):
        json_response = await fetch_ws(
            sanic_http_request,
            jsonrpc_request,
            batch_index)
    elif jsonrpc_request.upstream.url.startswith('http'):
        json_response = await fetch_http(
            sanic_http_request,
            jsonrpc_request,
            batch_index)
    else:
        raise ValueError(f'Bad url {jsonrpc_request.upstream.url}')

    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: BatchJsonRpcRequest
                         ) -> BatchJsonRpcResponse:
    requests = [dispatch_single(sanic_http_request, request, i)
                for i, request in enumerate(jsonrpc_requests)]
    return await asyncio.gather(*requests)
