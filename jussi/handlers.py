# -*- coding: utf-8 -*-
import asyncio
import concurrent.futures
import datetime
from time import perf_counter as perf
from typing import Coroutine

import cytoolz
import structlog

from async_timeout import timeout
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
    async with timeout(http_request.request_timeout):
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

# pylint: disable=protected-access, too-many-locals, no-member, unused-variable


async def monitor(http_request: HTTPRequest) -> HTTPResponse:
    app = http_request.app
    import inspect

    cache_data = []
    try:
        cache_group = app.config.cache_group
        cache_data.append({
            'cache.memory_cache': {
                'keys': len(cache_group._memory_cache._keys)
            }
        })
        for i, cache in enumerate(cache_group._read_caches):
            data = {
                'read_cache.pool.available': len(cache.client.connection_pool._available_connections),
                'read_cache.pool.in_use': len(cache.client.connection_pool._in_use_connections)
            }
            cache_data.append(data)
        for i, cache in enumerate(cache_group._write_caches):
            data = {
                'write_cache.pool.available': len(cache.client.connection_pool._available_connections),
                'write_cache.pool.in_use': len(cache.client.connection_pool._in_use_connections)
            }
            cache_data.append(data)
    except Exception as e:
        logger.error('error adding cache info', e=e)

    server_data = dict()
    try:
        frames = inspect.stack()
        server_frame = [f for f in frames if f.filename.endswith('sanic/server.py')][0]
        server = server_frame.frame.f_locals
        server_data = {
            'connections': len(server['connections']),
            'pid': str(server['pid']),
            'state': str(server['state'])
        }
        del frames
        del server_frame
        del server
    except Exception as e:
        logger.error('error adding cache info', e=e)

    ws_pools = []
    pools = http_request.app.config.websocket_pools
    try:
        for url, pool in pools.items():
            data = {
                'url': url,
                'queue': pool._queue.qsize,
                'in_use': len([ch._in_use for ch in pool._holders if ch._in_use is not None]),
                'ws_read_q_sizes': [ch._con.messages.qsize() for ch in pool._holders if ch._con]
            }
            ws_pools.append(data)
    except Exception as e:
        logger.error('error adding cache info', e=e)

    async_data = dict()
    try:
        tasks = asyncio.tasks.Task.all_tasks()
        grouped_tasks = cytoolz.groupby(lambda t: t._state, tasks)
        for k, v in grouped_tasks.items():
            grouped_tasks[k] = len(v)
        async_data = {
            'tasks.count': len(tasks),
            'tasks': grouped_tasks
        }
    except Exception as e:
        logger.error('error adding cache info', e=e)
    data = {
        'source_commit': http_request.app.config.args.source_commit,
        'docker_tag': http_request.app.config.args.docker_tag,
        'jussi_num': http_request.app.config.last_irreversible_block_num,
        'asyncio': async_data,
        'cache': cache_data,
        'server': server_data,
        'ws_pools': ws_pools

    }
    return response.json(data)
# pylint: enable=protected-access, too-many-locals, no-member, unused-variable

# pylint: disable=no-value-for-parameter, too-many-locals, too-many-branches, too-many-statements


async def fetch_ws(http_request: HTTPRequest,
                   jrpc_request: SingleJrpcRequest) -> SingleJrpcResponse:
    jrpc_request.timings.append((perf(), 'fetch_ws.enter'))
    pools = http_request.app.config.websocket_pools
    pool = pools[jrpc_request.upstream.url]
    upstream_request = jrpc_request.to_upstream_request()
    try:
        conn = await pool.acquire()
        jrpc_request.timings.append((perf(), 'fetch_ws.acquire'))
        await conn.send(upstream_request)
        jrpc_request.timings.append((perf(), 'fetch_ws.send'))
        upstream_response_json = await conn.recv()
        jrpc_request.timings.append((perf(), 'fetch_ws.response'))
        upstream_response = loads(upstream_response_json)
        await pool.release(conn)
        assert int(upstream_response.get('id')) == jrpc_request.upstream_id
        upstream_response['id'] = jrpc_request.id
        jrpc_request.timings.append((perf(), 'fetch_ws.exit'))
        return upstream_response

    except Exception as e:
        try:
            conn.terminate()
        except NameError:
            pass
        except Exception as e:
            logger.error('error while closing connection', e=e)
        raise e

# pylint: enable=no-value-for-parameter, too-many-locals, too-many-branches, too-many-statements


async def fetch_http(http_request: HTTPRequest,
                     jrpc_request: SingleJrpcRequest) -> SingleJrpcResponse:
    jrpc_request.timings.append((perf(), 'fetch_http.enter'))
    session = http_request.app.config.aiohttp['session']
    upstream_request = jrpc_request.to_upstream_request(as_json=False)

    async with session.post(jrpc_request.upstream.url,
                            json=upstream_request,
                            headers=jrpc_request.upstream_headers) as resp:
        jrpc_request.timings.append((perf(), 'fetch_http.response'))
        upstream_response = await resp.json(encoding='utf-8', content_type=None)
    upstream_response['id'] = jrpc_request.id
    jrpc_request.timings.append((perf(), 'fetch_http.exit'))
    return upstream_response
# pylint: enable=no-value-for-parameter


def dispatch_single(http_request: HTTPRequest,
                    jrpc_request) -> Coroutine:
    # pylint: disable=unexpected-keyword-arg
    if jrpc_request.upstream.url.startswith('ws'):
        response = fetch_ws(http_request, jrpc_request)
    elif jrpc_request.upstream.url.startswith('http'):
        response = fetch_http(http_request, jrpc_request)
    else:
        raise InvalidUpstreamURL(url=jrpc_request.upstream.url, reason='scheme')
    return response
