# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging

import async_timeout
from sanic import response

import ujson

from .errors import InvalidUpstreamURL
from .errors import UpstreamResponseError
from .typedefs import BatchJsonRpcRequest
from .typedefs import BatchJsonRpcResponse
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .utils import is_batch_jsonrpc

logger = logging.getLogger(__name__)

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
        'docker_tag': sanic_http_request.app.config.args.docker_tag,
        'jussi_num': sanic_http_request.app.config.last_irreversible_block_num
    })

# pylint: disable=no-value-for-parameter, too-many-locals


async def fetch_ws(sanic_http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    pools = sanic_http_request.app.config.websocket_pools
    pool = pools[jsonrpc_request.upstream.url]

    upstream_request = jsonrpc_request.to_upstream_request()
    conn = await pool.acquire()
    with async_timeout.timeout(jsonrpc_request.upstream.timeout):
        try:
            await conn.send(upstream_request)
            upstream_response_json = await conn.recv()
            upstream_response = ujson.loads(upstream_response_json)
            assert int(upstream_response.get('id')) == jsonrpc_request.upstream_id, \
                f'{upstream_response.get("id")} should be {jsonrpc_request.upstream_id}'

            upstream_response['id'] = jsonrpc_request.id
            return upstream_response

        except AssertionError as e:
            request_info = jsonrpc_request.log_extra(
                upstream_request=upstream_request)
            try:
                request_info['upstream_response'] = upstream_response
            except NameError:
                pass
            await pool.terminate_connection(conn)
            raise UpstreamResponseError(sanic_request=sanic_http_request,
                                        exception=e,
                                        **request_info)
        except Exception as e:
            request_info = jsonrpc_request.log_extra(
                upstream_request=upstream_request)
            logger.exception(f'fetch_ws failed', extra=request_info)
            await pool.terminate_connection(conn)
            raise e
        finally:
            await pool.release(conn)


async def fetch_http(sanic_http_request: HTTPRequest,
                     jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:

    session = sanic_http_request.app.config.aiohttp['session']
    upstream_request = jsonrpc_request.to_upstream_request(as_json=False)
    async with session.post(jsonrpc_request.upstream.url,
                            json=upstream_request,
                            headers=jsonrpc_request.upstream_headers,
                            timeout=jsonrpc_request.upstream.timeout) as resp:

        upstream_response = await resp.json(encoding='utf-8', content_type=None)
        upstream_response['id'] = jsonrpc_request.id
        return upstream_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    # pylint: disable=unexpected-keyword-arg
    if jsonrpc_request.upstream.url.startswith('ws'):
        json_response = await fetch_ws(
            sanic_http_request,
            jsonrpc_request)
    elif jsonrpc_request.upstream.url.startswith('http'):
        json_response = await fetch_http(
            sanic_http_request,
            jsonrpc_request)
    else:
        raise InvalidUpstreamURL(url=jsonrpc_request.upstream.url)

    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: BatchJsonRpcRequest
                         ) -> BatchJsonRpcResponse:
    requests = [dispatch_single(sanic_http_request, request)
                for request in jsonrpc_requests]
    return await asyncio.gather(*requests)
