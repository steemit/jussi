# -*- coding: utf-8 -*-
import argparse
import logging
import os
import ujson

import asyncio

from sanic import Sanic
from sanic import response

from sanic.log import log

import websockets
from jsonrpcclient import config as client_config
from jsonrpcclient.websockets_client import WebSocketsClient

import aiohttp
import pygtrie
from diskcache import Cache

from logging_config import LOGGING
from middlewares import jsonrpc_id_to_str
from middlewares import add_jussi_attrs
from middlewares import caching_middleware
from exceptions import JsonRpcServerError
from utils import get_upstream
from cache import cache_get
from cache import cache_set
from cache.serializers import JSONDisk

# init logging
LOG_LEVEL = getattr(logging, os.environ.get('LOG_LEVEL', 'DEBUG'))
LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
LOGGING['loggers']['network']['level'] = LOG_LEVEL

app = Sanic(__name__, log_config=LOGGING)
logger = logging.getLogger('sanic')

DEFAULT_CACHE_TTL = 3
NO_CACHE_TTL = -1
NO_CACHE_EXPIRE_TTL = 0

# add individual method cache settings here
METHOD_CACHE_SETTINGS = (('get_block', 'steemd_websocket_url',
                          NO_CACHE_EXPIRE_TTL), )


async def fetch_ws(app, jussi, jsonrpc_request):
    logger.debug('%s --> %s', jsonrpc_request, jussi.upstream_url)
    session = app.config.aiohttp['session']
    async with session.ws_connect(jussi.upstream_url) as ws:
        ws.send_json(jsonrpc_request)
        response = await ws.receive_json()
        logger.debug('%s --> %s', jussi.upstream_url, response)
        return response


async def http_post(app, jussi, jsonrpc_request):
    session = app.config.aiohttp['session']
    logger.debug('%s --> %s', jsonrpc_request, jussi.upstream_url)
    async with session.post(jussi.upstream_url, json=jsonrpc_request) as resp:
        response = await resp.json()
        logger.debug('%s --> %s', jussi.upstream_url, response)
        return response


async def dispatch_single(sanic_http_request, jsonrpc_request, jrpc_req_index):
    app = sanic_http_request.app
    jussi_attrs = sanic_http_request['jussi']

    # get attrs for this request id part of batch request
    if isinstance(jussi_attrs, list):
        jussi_attrs = jussi_attrs[jrpc_req_index]

    # return cached response if possible
    response = await cache_get(app, jussi_attrs)
    if response:
        return response

    if jussi_attrs.is_ws:
        response = await fetch_ws(app, jussi_attrs, jsonrpc_request)
    else:
        response = await http_post(app, jussi_attrs, jsonrpc_request)

    asyncio.ensure_future(cache_set(app, response, jussi_attrs=jussi_attrs))
    return response


async def dispatch_batch(sanic_http_request, jsonrpc_requests):
    return asyncio.gather([
        dispatch_single(sanic_http_request, jsonrpc_request, jrpc_req_index)
        for jsonrpc_request, jrpc_req_index in enumerate(jsonrpc_requests)
    ])


@app.route('/', methods=['POST'])
async def handle(sanic_http_request):
    app = sanic_http_request.app

    # retreive parsed jsonrpc_requests after request middleware processing
    jsonrpc_requests = sanic_http_request.json

    # make upstream requests
    if sanic_http_request['jussi_is_batch']:
        jsonrpc_responses = await dispatch_batch(sanic_http_request,
                                                 jsonrpc_requests)
        # handle caching of batch response
        cache_key = sanic_http_request['jussi_batch_key']
        cache_expire = sanic_http_request['jussi_batch_ttl']
        asyncio.ensure_future(
            cache_set(app, response, key=cache_key, expire=cache_expire))
        return response.json(jsonrpc_responses)
    else:
        jsonrpc_response = await dispatch_single(sanic_http_request,
                                                 jsonrpc_requests, 0)
        return response.json(jsonrpc_response)


@app.exception(JsonRpcServerError)
def handle_errors(request, exception):
    return response.json(str(exception))


# register listeners
# Even though these functions can be async, use sync to assure they are applied
# in the order they are decorated


# before server start
@app.listener('before_server_start')
def setup_jsonrpc(app, loop):
    client_config.validate = False


@app.listener('before_server_start')
def setup_statsd(app, loop):
    logger.info('before_server_start -> setup_statsd')
    args = app.config.args
    if args.statsd_host:
        app.config.statsd = {
            'host': args.statsd_host,
            'port': args.statsd_port,
            'prefix': args.stats_prefix
        }


@app.listener('before_server_start')
def setup_middlewares(app, loop):
    """Add middlewares to be applied in the order they are added

    Args:
        app:
        loop:

    Returns:

    """
    logger.info('before_server_start -> setup_middlewares')
    app.request_middleware.append(jsonrpc_id_to_str)
    app.request_middleware.append(add_jussi_attrs)
    app.request_middleware.append(caching_middleware)


@app.listener('before_server_start')
def setup_cache(app, loop):
    logger.info('before_server_start -> setup_cache')
    cache = Cache(
        args.cache_dir, size_limit=int(20e9), disk=JSONDisk)  # ~ 20GB

    cache_config = dict()
    cache_config['cache'] = cache
    cache_config['default_cache_ttl'] = DEFAULT_CACHE_TTL
    cache_config['no_cache_ttl'] = NO_CACHE_TTL
    cache_config['no_cache_expire_ttl'] = NO_CACHE_EXPIRE_TTL

    app.config.cache_config = cache_config
    app.config.cache = cache


@app.listener('before_server_start')
def setup_aiohttp_session(app, loop):
    logger.info('before_server_start -> setup_aiohttp_session')
    aio = dict(session=aiohttp.ClientSession(
        skip_auto_headers=['User-Agent'],
        loop=loop,
        json_serialize=ujson.dumps,
        headers={'Content-Type': 'application/json'}))
    app.config.aiohttp = aio


@app.listener('before_server_start')
async def setup_ws_client(app, loop):
    logger.info('before_server_start -> setup_ws_client')
    args = app.config.args
    aio_session = app.config.aiohttp['session']
    async with aio_session.ws_connect(args.steemd_websocket_url) as ws:
        app.config.aio_ws_client = ws


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


if __name__ == '__main__':

    # parse CLI args and add them to app.config for use by registered listeners
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_host', type=str, default='0.0.0.0')
    parser.add_argument('--server_port', type=int, default=9000)
    parser.add_argument(
        '--server_workers', type=int, default=os.cpu_count() - 1)
    parser.add_argument('--server_debug', type=bool, default=False)
    parser.add_argument(
        '--steemd_url', type=str, default='https://steemd.steemit.com')
    parser.add_argument(
        '--steemd_websocket_url', type=str, default='wss://steemd.steemit.com')
    parser.add_argument(
        '--sbds_url', type=str, default='https://sbds.steemit.com')
    parser.add_argument('--statsd_host', type=str)
    parser.add_argument('--statsd_port', type=int, default=8125)
    parser.add_argument('--statsd_prefix', type=str, default='jussi')
    parser.add_argument('--cache_dir', type=str, default='/tmp/jussi-cache')
    args = parser.parse_args()
    app.config.args = args

    LOGGING['loggers']['sanic']['level'] = LOG_LEVEL
    LOGGING['loggers']['network']['level'] = LOG_LEVEL

    # run app
    logger.info('app.run')
    app.run(
        host=args.server_host,
        port=args.server_port,
        debug=args.server_debug,
        workers=args.server_workers,
        log_config=LOGGING)
