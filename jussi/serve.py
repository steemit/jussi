# -*- coding: utf-8 -*-
import logging
import os
import ujson
import sys
import asyncio

import uvloop
import aiohttp
from aiohttp import web
import websockets
from jsonrpcclient import config as client_config
from jsonrpcclient.aiohttp_client import aiohttpClient
from jsonrpcclient.websockets_client import WebSocketsClient
from jsonrpcserver import config as server_config


from methods import methods
from utils import patch_requests
from utils import patch_responses
from utils import split_namespaced_method

log_level = getattr(logging, os.environ.get('LOG_LEVEL', 'ERROR'))
logging.basicConfig(level=log_level, stream=sys.stdout)
logger = logging.getLogger('jussi')

server_config.schema_validation = False
client_config.validate = False

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

app = web.Application()

# health check route jussi.health
@methods.add
async def jussi(namespaced_method, *args, **kwargs):
    return 'ok'


@methods.add
async def sbds(namespaced_method, *args, **kwargs):
    return await forward(namespaced_method, app['sbds_url'], *args, **kwargs)


@methods.add
async def steemd(namespaced_method, *args, **kwargs):
    _, method = split_namespaced_method(namespaced_method)
    return await forward(method, app['steemd_url'], *args, **kwargs)



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


def pre_request_hook(requests):
    if isinstance(requests, list):
        return list(map(patch_requests, requests))
    else:
        return patch_requests(requests)


def pre_response_hook(responses):
    if isinstance(responses, list):
        return map(patch_responses, responses)
    else:
        return patch_responses(responses)


async def handle(request):
    requests = await request.json(loads=ujson.loads)
    requests = pre_request_hook(requests)
    responses = await methods.dispatch(requests)
    responses = pre_response_hook(responses)
    return web.json_response(responses)


if __name__ == '__main__':
    import argparse
    # pylint: disable=invalid-name
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
    args = parser.parse_args()

    app['steemd_url'] = args.steemd_url
    app['sbds_url'] = args.sbds_url
    app['steemd_websocket_url'] = args.steemd_websocket_url
    app.router.add_post('/', handle)

    web.run_app(app, path=args.server_path, port=args.server_port)
