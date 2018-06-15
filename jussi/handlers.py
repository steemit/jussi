# -*- coding: utf-8 -*-

import asyncio
import datetime
from time import perf_counter as perf
from concurrent.futures import CancelledError

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
from .typedefs import SingleJrpcRequest
from .typedefs import SingleJrpcResponse


logger = structlog.get_logger(__name__)

# path /


async def handle_jsonrpc(http_request: HTTPRequest) -> HTTPResponse:
    # retreive parsed jsonrpc_requests after request middleware processing
    http_request.timings.append((perf(), 'handle_jsonrpc.enter'))
    # make upstream requests
    if http_request.is_single_jrpc:
        jsonrpc_response = await dispatch_single(http_request,
                                                 http_request.jsonrpc)
    else:
        futures = [dispatch_single(http_request, request)
                   for request in http_request.jsonrpc]
        jsonrpc_response = await asyncio.gather(*futures)
    http_request.timings.append((perf(), 'handle_jsonrpc.exit'))
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
                   jrpc_request: SingleJrpcRequest) -> SingleJrpcResponse:
    jrpc_request.timings.append((perf(), 'fetch_ws.enter'))
    pools = http_request.app.config.websocket_pools
    pool = pools[jrpc_request.upstream.url]
    upstream_request = jrpc_request.to_upstream_request()
    try:
        async with timeout(jrpc_request.upstream.timeout):
            conn = await pool.acquire()
            jrpc_request.timings.append((perf(), 'fetch_ws.acquire'))
            await conn.send(upstream_request)
            jrpc_request.timings.append((perf(), 'fetch_ws.send'))
            upstream_response_json = await conn.recv()
            jrpc_request.timings.append((perf(), 'fetch_ws.response'))
        await pool.release(conn)
        upstream_response = loads(upstream_response_json)
        assert int(upstream_response.get('id')) == jrpc_request.upstream_id
        upstream_response['id'] = jrpc_request.id
        jrpc_request.timings.append((perf(), 'fetch_ws.exit'))
        return upstream_response

    except (TimeoutError, CancelledError) as e:
        raise RequestTimeoutError(http_request=http_request,
                                  jrpc_request=jrpc_request,
                                  exception=e,
                                  upstream_request=upstream_request)
    except AssertionError as e:
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=upstream_response
                                    )
    except ConnectionClosed as e:
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jrpc_request,
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
                                    jrpc_request=jrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=response,
                                    log_traceback=True)


async def fetch_http(http_request: HTTPRequest,
                     jrpc_request: SingleJrpcRequest) -> SingleJrpcResponse:
    jrpc_request.timings.append((perf(), 'fetch_http.enter'))
    session = http_request.app.config.aiohttp['session']
    upstream_request = jrpc_request.to_upstream_request(as_json=False)
    try:

        async with session.post(jrpc_request.upstream.url,
                                json=upstream_request,
                                headers=jrpc_request.upstream_headers,
                                timeout=jrpc_request.upstream.timeout) as resp:
            jrpc_request.timings.append((perf(), 'fetch_http.sent'))
            upstream_response = await resp.json(encoding='utf-8', content_type=None)
        jrpc_request.timings.append((perf(), 'fetch_http.response'))
    except Exception as e:
        try:
            response = upstream_response
        except NameError:
            response = None
        raise UpstreamResponseError(http_request=http_request,
                                    jrpc_request=jrpc_request,
                                    exception=e,
                                    upstream_request=upstream_request,
                                    upstream_response=response)
    upstream_response['id'] = jrpc_request.id
    jrpc_request.timings.append((perf(), 'fetch_http.exit'))
    return upstream_response
# pylint: enable=no-value-for-parameter


async def dispatch_single(http_request: HTTPRequest,
                          jrpc_request) -> SingleJrpcResponse:
    # pylint: disable=unexpected-keyword-arg
    if jrpc_request.upstream.url.startswith('ws'):
        response = await fetch_ws(http_request, jrpc_request)
    elif jrpc_request.upstream.url.startswith('http'):
        response = await fetch_http(http_request, jrpc_request)
    else:
        raise InvalidUpstreamURL(url=jrpc_request.upstream.url, reason='scheme')
    return response
