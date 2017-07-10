# -*- coding: utf-8 -*-
import argparse
import asyncio
import datetime
import logging
import os

import aiohttp
import funcy
import pygtrie
import ujson
import websockets
from sanic import Sanic
from sanic import response
from sanic.exceptions import SanicException
from statsd import StatsClient

from jussi.cache import cache_get
from jussi.cache import cache_json_response
from jussi.cache import setup_caches
from jussi.logging_config import LOGGING
from jussi.middlewares import add_jussi_attrs
from jussi.middlewares import caching_middleware
from jussi.middlewares import finalize_timers
from jussi.middlewares import log_stats
from jussi.middlewares import start_stats
from jussi.utils import return_bytes
from jussi.utils import websocket_conn

# init logging
LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'INFO'))
LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
LOGGING['loggers']['network']['level'] = LOG_LEVEL

# pylint: disable=unused-variable
app = Sanic(__name__, log_config=LOGGING)
logger = logging.getLogger('sanic')

DEFAULT_CACHE_TTL = 3
NO_CACHE_TTL = -1
NO_CACHE_EXPIRE_TTL = 0

# add individual method cache settings here
METHOD_CACHE_SETTINGS = (('get_block', 'steemd_websocket_url',
                          NO_CACHE_EXPIRE_TTL),
                         ('get_block_header', 'steemd_websocket_url',
                          NO_CACHE_EXPIRE_TTL),
                         ('get_global_dynamic_properties',
                          'steemd_websocket_url', 1))

# pylint: disable=unused-argument


@funcy.log_calls(logger.debug)
@return_bytes
@websocket_conn
async def fetch_ws(app, jussi, jsonrpc_request):
    ws = app.config.websocket_client
    await ws.send(ujson.dumps(jsonrpc_request).encode())
    response = await ws.recv()
    return response


@funcy.log_calls(logger.debug)
async def fetch_http(app, jussi, jsonrpc_request):
    session = app.config.aiohttp['session']
    async with session.post(jussi.upstream_url, json=jsonrpc_request) as resp:
        bytes_response = await resp.read()
        return bytes_response


async def dispatch_single(sanic_http_request, jsonrpc_request, jrpc_req_index):
    app = sanic_http_request.app
    jussi_attrs = sanic_http_request['jussi']

    # get attrs for this request id part of batch request
    if sanic_http_request['jussi_is_batch']:
        jussi_attrs = jussi_attrs[jrpc_req_index]

    # stats/logging
    def prefix(name):
        return '%s.%s' % (jussi_attrs.log_prefix, name)

    sanic_http_request['statsd'].incr('%s.%s' % (jussi_attrs.namespace,
                                                 jussi_attrs.method_name))

    # return cached response if possible
    with sanic_http_request['timers'][prefix('dispatch_single_caching_check')]:
        response = await cache_get(sanic_http_request, jussi_attrs)
    if response:
        return response

    if jussi_attrs.is_ws:
        with sanic_http_request['timers'][prefix('fetch_ws')]:
            bytes_response = await fetch_ws(app, jussi_attrs, jsonrpc_request)
    else:
        with sanic_http_request['timers'][prefix('fetch_http')]:
            bytes_response = await fetch_http(app, jussi_attrs,
                                              jsonrpc_request)

    asyncio.ensure_future(
        cache_json_response(sanic_http_request, bytes_response, jussi_attrs=jussi_attrs))
    return bytes_response


async def dispatch_batch(sanic_http_request, jsonrpc_requests):
    with sanic_http_request['timers']['batch_requests']:
        responses = await asyncio.gather(* [
            dispatch_single(sanic_http_request, jsonrpc_request,
                            jrpc_req_index)
            for jrpc_req_index, jsonrpc_request in enumerate(jsonrpc_requests)
        ])
    json_responses = []
    for r in responses:
        if isinstance(r, bytes):
            json_responses.append(ujson.loads(r.decode()))
        elif isinstance(r, str):
            json_responses.append(ujson.loads(r))
    return ujson.dumps(json_responses).encode()


@app.post('/')
async def handle_jsonrpc(sanic_http_request):
    app = sanic_http_request.app

    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json

    # make upstream requests

    if sanic_http_request['jussi_is_batch']:
        jsonrpc_response = await dispatch_batch(sanic_http_request,
                                                jsonrpc_requests)
    else:
        jsonrpc_response = await dispatch_single(sanic_http_request,
                                                 jsonrpc_requests, 0)

    if isinstance(jsonrpc_response, bytes):
        return response.raw(jsonrpc_response, content_type='application/json')
    elif isinstance(jsonrpc_response, (dict, list)):
        return response.json(jsonrpc_response)

    return response.text(jsonrpc_response, content_type='application/json')


# health check routes
@app.get('/')
async def handle_root_health(sanic_http_request):
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat()
    })


@app.get('/health')
async def handle_health(sanic_http_request):
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat()
    })


@app.exception(SanicException)
def handle_errors(request, exception):
    """handles all errors

    Args:
        request:
        exception:

    Returns:

    """
    logger.exception('%s caused %s', request, exception)
    status_code = getattr(exception, 'status_code', 502)
    message = str(exception) or 'Gateway Error'
    return response.json(status=status_code, body=
        {
            'error': 'Gateway Error',
            'status_code': status_code
        })


# register listeners
# Even though these functions can be async, use sync to assure they are applied
# in the order they are decorated


# pylint: disable=unused-argument
# before server start
@app.listener('before_server_start')
def setup_statsd(app, loop):
    logger.info('before_server_start -> setup_statsd')
    args = app.config.args

    config = {
        'host': args.statsd_host,
        'port': args.statsd_port,
        'prefix': args.statsd_prefix
    }
    app.config.statsd_client = StatsClient(**config)


@app.listener('before_server_start')
def setup_middlewares(app, loop):
    logger.info('before_server_start -> setup_middlewares')
    app.request_middleware.append(start_stats)
    app.request_middleware.append(add_jussi_attrs)
    app.request_middleware.append(caching_middleware)

    #app.response_middleware.append(finalize_timers)
    #app.response_middleware.append(log_stats)


@app.listener('before_server_start')
async def setup_cache(app, loop):
    logger.info('before_server_start -> setup_cache')
    args = app.config.args
    caches = await setup_caches(app, loop)
    for cache_alias in caches.get_config().keys():
        logger.info('before_server_start -> setup_cache caches=%s', cache_alias)
    active_caches = [caches.get(alias) for alias in caches.get_config().keys()]

    cache_config = dict()
    cache_config['default_cache_ttl'] = DEFAULT_CACHE_TTL
    cache_config['no_cache_ttl'] = NO_CACHE_TTL
    cache_config['no_cache_expire_ttl'] = NO_CACHE_EXPIRE_TTL


    app.config.cache_config = cache_config
    app.config.caches = active_caches


@app.listener('before_server_start')
def setup_aiohttp_session(app, loop):
    """use one session for http connection pooling

    Args:
        app:
        loop:

    Returns:

    """
    logger.info('before_server_start -> setup_aiohttp_session')
    aio = dict(session=aiohttp.ClientSession(
        skip_auto_headers=['User-Agent'],
        loop=loop,
        json_serialize=ujson.dumps,
        headers={'Content-Type': 'application/json'}))
    app.config.aiohttp = aio


@app.listener('before_server_start')
async def setup_websocket_connection(app, loop):
    """use one ws connection (per worker) to avoid reconnection

    Args:
        app:
        loop:

    Returns:

    """
    logger.info('before_server_start -> setup_ws_client')
    args = app.config.args
    app.config.websocket_kwargs = dict(
        uri=args.steemd_websocket_url, max_size=int(2e6), max_queue=200)
    app.config.websocket_client = await websockets.connect(
        **app.config.websocket_kwargs)


@app.listener('before_server_start')
async def config_upstreams(app, loop):
    logger.info('before_server_start -> config_upstreams')
    args = app.config.args

    upstreams = pygtrie.StringTrie(separator='.')

    # steemd methods aren't namespaced so this is the steemd default entry
    upstreams[''] = dict(url=args.steemd_websocket_url, ttl=DEFAULT_CACHE_TTL)

    upstreams['sbds'] = dict(url=args.sbds_url, ttl=30)

    for m in METHOD_CACHE_SETTINGS:
        name, url_name, ttl = m
        url = getattr(args, url_name)
        upstreams[name] = dict(url=url, ttl=ttl)

    app.config.upstreams = upstreams


# before server stop
@app.listener('before_server_stop')
def close_aiohttp_session(app, loop):
    logger.info('before_server_stop -> close_aiohttp_session')
    session = app.config.aiohttp['session']
    session.close()


@app.listener('before_server_stop')
def close_websocket_connection(app, loop):
    logger.info('before_server_stop -> close_aiohttp_session')
    session = app.config.aiohttp['session']
    session.close()


def main():
    # parse CLI args and add them to app.config for use by registered listeners
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_host', type=str, default='0.0.0.0')
    parser.add_argument('--server_port', type=int, default=9000)
    parser.add_argument('--server_workers', type=int, default=os.cpu_count())
    parser.add_argument(
        '--steemd_websocket_url',
        type=str,
        default='wss://steemd.steemitdev.com')
    parser.add_argument(
        '--sbds_url', type=str, default='https://sbds.steemit.com')
    parser.add_argument('--redis_host', type=str, default=None)
    parser.add_argument('--redis_port', type=int, default=6379)
    parser.add_argument('--redis_namespace', type=str, default='jussi')
    parser.add_argument('--statsd_host', type=str, default='localhost')
    parser.add_argument('--statsd_port', type=int, default=8125)
    parser.add_argument('--statsd_prefix', type=str, default='jussi')
    args = parser.parse_args()
    app.config.args = args

    # run app
    logger.info('app.run')
    app.run(
        host=args.server_host,
        port=args.server_port,
        workers=args.server_workers,
        log_config=LOGGING)


if __name__ == '__main__':
    main()
