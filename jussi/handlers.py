# -*- coding: utf-8 -*-

import asyncio
import datetime
from time import perf_counter


from async_timeout import timeout
import structlog
from sanic import response

from ujson import loads
from websockets.exceptions import ConnectionClosed

from .errors import InvalidUpstreamURL
from .errors import RequestTimeoutError
from .errors import UpstreamResponseError
from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse


logger = structlog.get_logger(__name__)

# path /


async def handle_jsonrpc(http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    http_request.timings['handle_jsonrpc.enter'] = perf_counter()
    # make upstream requests
    if http_request.is_single_jrpc:
        jsonrpc_response = await dispatch_single(http_request,
                                                 http_request.jsonrpc)
    else:
        futures = [dispatch_single(http_request, request)
                   for request in http_request.jsonrpc]
        jsonrpc_response = await asyncio.gather(*futures)
    http_request.timings['handle_jsonrpc.exit'] = perf_counter()
    return response.json(jsonrpc_response)


async def healthcheck(http_request: HTTPRequest) -> HTTPResponse:
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat(),
        'source_commit': http_request.app.config.args.source_commit,
        'docker_tag': http_request.app.config.args.docker_tag,
        'jussi_num': http_request.app.config.last_irreversible_block_num
    })

# pylint: disable=no-value-for-parameter, too-many-locals


async def fetch_ws(http_request: HTTPRequest,
                   jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    jsonrpc_request.timings['fetch_ws.enter'] = perf_counter()
    pools = http_request.app.config.websocket_pools
    pool = pools[jsonrpc_request.upstream.url]
    upstream_request = jsonrpc_request.to_upstream_request()
    try:
        with timeout(jsonrpc_request.upstream.timeout):
            conn = await pool.acquire()
            jsonrpc_request.timings['fetch_ws.acquired'] = perf_counter()
            await conn.send(upstream_request)
            jsonrpc_request.timings['fetch_ws.sent'] = perf_counter()
            upstream_response_json = await conn.recv()
            jsonrpc_request.timings['fetch_ws.response'] = perf_counter()
        await pool.release(conn)
        upstream_response = loads(upstream_response_json)
        assert int(upstream_response.get('id')) == jsonrpc_request.upstream_id
        upstream_response['id'] = jsonrpc_request.id
        jsonrpc_request.timings['fetch_ws.exit'] = perf_counter()
        return upstream_response

    except TimeoutError as e:
        raise RequestTimeoutError(http_request=http_request,
                                  jrpc_request=jsonrpc_request,
                                  exception=e,
                                  upstream_request=upstream_request)
    except AssertionError as e:
        await pool.terminate_connection(conn)
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jsonrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=upstream_response
                                    )
    except ConnectionClosed as e:
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jsonrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request)
    except Exception as e:
        try:
            await pool.terminate_connection(conn)
        except NameError:
            pass
        try:
            response = upstream_response
        except NameError:
            response = None
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jsonrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=response)


async def fetch_http(http_request: HTTPRequest,
                     jsonrpc_request: SingleJsonRpcRequest) -> SingleJsonRpcResponse:
    jsonrpc_request.timings['fetch_http.enter'] = perf_counter()
    session = http_request.app.config.aiohttp['session']
    upstream_request = jsonrpc_request.to_upstream_request(as_json=False)
    try:

        async with session.post(jsonrpc_request.upstream.url,
                                json=upstream_request,
                                headers=jsonrpc_request.upstream_headers,
                                timeout=jsonrpc_request.upstream.timeout) as resp:
            jsonrpc_request.timings['fetch_http.sent'] = perf_counter()
            upstream_response = await resp.json(encoding='utf-8', content_type=None)
            jsonrpc_request.timings['fetch_http.response'] = perf_counter()
    except Exception as e:
        try:
            response = upstream_response
        except NameError:
            response = None
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jsonrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=response)
    upstream_response['id'] = jsonrpc_request.id
    jsonrpc_request.timings['fetch_http.exit'] = perf_counter()
    return upstream_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(http_request: HTTPRequest,
                          jsonrpc_request) -> SingleJsonRpcResponse:
    # pylint: disable=unexpected-keyword-arg
    if jsonrpc_request.upstream.url.startswith('ws'):
        json_response = await fetch_ws(
            http_request,
            jsonrpc_request)
    elif jsonrpc_request.upstream.url.startswith('http'):
        json_response = await fetch_http(
            http_request,
            jsonrpc_request)
    else:
        raise InvalidUpstreamURL(url=jsonrpc_request.upstream.url, reason='scheme')

    return json_response
