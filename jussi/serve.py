# -*- coding: utf-8 -*-
import argparse
import logging
import os
import ujson
import sys
import asyncio

import uvloop
import aiohttp
from aiohttp import web
import async_timeout
import websockets
from jsonrpcclient import config as client_config
from jsonrpcclient.aiohttp_client import aiohttpClient
from jsonrpcclient.websockets_client import WebSocketsClient
from jsonrpcserver import config as server_config


from .methods import methods
from .utils import patch_requests
from .utils import patch_responses
from .utils import split_namespaced_method

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
app = web.Application(loop=loop)

STEEMD_WEBSOCKETS_METHOD_LIST = frozenset(
    'none'
)

# health check route jussi.health
@methods.add
async def jussi(namespaced_method, *args, **kwargs):
    return 'ok'


@methods.add
async def sbds(namespaced_method, *args, **kwargs):
    return await forward(namespaced_method, app['sbds_url'], *args, **kwargs)


@methods.add
async def steemd(namespaced_method, *args, **kwargs):
    _, steemd_method = split_namespaced_method(namespaced_method)
    if steemd_method in STEEMD_WEBSOCKETS_METHOD_LIST:
        return await forward_websocket(steemd_method,
                                       app['steemd_websocket_url'], *args, **kwargs)
    else:
        return await forward(steemd_method,
                             app['steemd_url'], *args, **kwargs)


async def forward(method, url, *args, **kwargs):
    async with aiohttp.ClientSession(
            json_serialize=ujson.dumps,
            headers={'Content-Type': 'application/json'}) as session:
        client = aiohttpClient(session, url)
        response = await client.request(method, *args, **kwargs)
        return response


async def forward_websocket(method, url, *args, **kwargs):
    async with websockets.connect(url) as ws:
        response = await WebSocketsClient(ws).request(method,
                                                      app['steemd_websocket_url'],
                                                      *args, **kwargs)
    return response


async def pre_upstream_request_hook(aio_http_request, json_rpc_requests):
    if isinstance(json_rpc_requests, list):
        return list(map(patch_requests, json_rpc_requests))
    else:
        return patch_requests(json_rpc_requests)


async def pre_response_hook(aio_http_request, json_rpc_requests, json_rpc_responses):
    if isinstance(json_rpc_responses, list):
        return map(patch_responses, json_rpc_responses)
    else:
        return patch_responses(json_rpc_responses)


async def handle(aio_http_request):
    # parse aio http request into json rpc request[s]
    json_rpc_requests = await aio_http_request.json(loads=ujson.loads)

    # hook called before upstream request
    json_rpc_requests = await pre_upstream_request_hook(aio_http_request,
                                                        json_rpc_requests)

    # make upstream request
    json_rpc_responses = await methods.dispatch(json_rpc_requests)

    # hook called before returning response
    json_rpc_responses = await pre_response_hook(aio_http_request,
                                                 json_rpc_requests,
                                                 json_rpc_responses)

    return web.json_response(json_rpc_responses)


def setup_middlewares(app):
    return app


def setup_json_rpc(app):
    server_config.schema_validation = False
    client_config.validate = False


def init(loop, argv, app):
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_path')
    parser.add_argument('--server_port', type=int)
    parser.add_argument(
        '--steemd_url',
        type=str,
        default='https://steemd.steemitdev.com')
    parser.add_argument(
        '--steemd_websocket_url',
        type=str,
        default='wss://steemd.steemitdev.com')
    parser.add_argument(
        '--sbds_url',
        type=str,
        default='https://sbds.steemitdev.com')
    parser.add_argument(
        '--statsd_host',
        type=str,
        default='localhost')
    parser.add_argument(
        '--statsd_port',
        type=int,
        default=8125)
    parser.add_argument(
        '--statsd_prefix',
        type=str,
        default='jussi')

    STATSD_HOST = 'localhost'
    STATSD_PORT = 8125
    STATSD_PREFIX = None
    STATSD_MAXUDPSIZE = 512

    args = parser.parse_args(argv)

    # setup application and extensions
    #app = web.Application(loop=loop)

    # add vars to app config
    app['config'] = dict()
    app['config']['server_port'] = args.server_port
    app['config']['server_path'] = args.server_path
    app['config']['steemd_url'] = args.steemd_url
    app['config']['steemd_websocket_url'] = args.steemd_websocket_url
    app['config']['sbds_url'] = args.sbds_url


    # create connection to the database, etc on app startup
    #app.on_startup.append(<run me at app startup>)

    # shutdown db connection, etc on app exit
    #app.on_cleanup.append(<run me at app exit>)

    app.router.add_post('/', handle)

    # add middlewares
    setup_middlewares(app)

    # setup json rpc
    setup_json_rpc(app)

    return app


def main(argv, app=app):
    # init logging
    log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'ERROR'))
    logging.basicConfig(level=log_level, stream=sys.stdout)

    app = init(loop, argv, app)

    web.run_app(app,path=app['config']['path'],
                    port=app['config']['port'])



if __name__ == '__main__':
    main(sys.argv[1:])
