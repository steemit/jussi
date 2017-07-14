# -*- coding: utf-8 -*-

import asyncio
import datetime
import logging

import funcy
import ujson
from sanic import response

from jussi.cache import cache_get
from jussi.cache import cache_json_response
from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcRequest
from jussi.typedefs import JussiAttrs
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import WebApp
from jussi.utils import websocket_conn

logger = logging.getLogger('sanic')


async def handle_jsonrpc(sanic_http_request: HTTPRequest) -> HTTPResponse:

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


# pylint: disable=unused-argument
async def healthcheck(sanic_http_request: HTTPRequest) -> HTTPResponse:
    return response.json({
        'status': 'OK',
        'datetime': datetime.datetime.utcnow().isoformat()
    })


@funcy.log_calls(logger.debug)
@websocket_conn
async def fetch_ws(app,
                   jussi: JussiAttrs,
                   jsonrpc_request: SingleJsonRpcRequest) -> dict:
    ws = app.config.websocket_client
    await ws.send(ujson.dumps(jsonrpc_request).encode())
    json_response = await ws.recv()
    return json_response


@funcy.log_calls(logger.debug)
async def fetch_http(app: WebApp,
                     jussi: JussiAttrs,
                     jsonrpc_request: SingleJsonRpcRequest) -> dict:
    session = app.config.aiohttp['session']
    async with session.post(jussi.upstream_url, json=jsonrpc_request) as resp:
        json_response = await resp.json()
        return json_response


async def dispatch_single(sanic_http_request: HTTPRequest,
                          jsonrpc_request: SingleJsonRpcRequest,
                          jrpc_req_index: int) -> dict:
    app = sanic_http_request.app
    jussi_attrs = sanic_http_request['jussi']

    # get attrs for this request id part of batch request
    if sanic_http_request['jussi_is_batch']:
        jussi_attrs = jussi_attrs[jrpc_req_index]

    # return cached response if possible

    response = await cache_get(sanic_http_request, jussi_attrs)
    if response:
        return response

    if jussi_attrs.is_ws:
        json_response = await fetch_ws(app, jussi_attrs, jsonrpc_request)
    else:
        json_response = await fetch_http(app, jussi_attrs, jsonrpc_request)

    asyncio.ensure_future(
        cache_json_response(
            sanic_http_request, json_response, jussi_attrs=jussi_attrs))
    return json_response


async def dispatch_batch(sanic_http_request: HTTPRequest,
                         jsonrpc_requests: JsonRpcRequest) -> bytes:

    responses = await asyncio.gather(* [
        dispatch_single(sanic_http_request, jsonrpc_request, jrpc_req_index)
        for jrpc_req_index, jsonrpc_request in enumerate(jsonrpc_requests)
    ])

    return ujson.dumps(responses).encode()
