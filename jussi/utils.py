# -*- coding: utf-8 -*-
import asyncio
import functools
import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Callable
from typing import Optional
from typing import Tuple
from typing import Union

import websockets
from funcy.decorators import decorator
from sanic.exceptions import InvalidUsage

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JussiAttrs
from jussi.typedefs import SingleJsonRpcRequest

logger = logging.getLogger('sanic')


# decorators
@decorator
def apply_single_or_batch(call: Callable) -> Callable:
    """Decorate func to apply func to single or batch jsonrpc_requests
    """
    if isinstance(call.single_jsonrpc_request, list):
        results = []
        for request in call.jsonrpc_request:
            results.append(call(single_jsonrpc_request=request))
        return results
    return call()


@decorator
async def websocket_conn(call: Callable) -> Callable:
    """Decorate func to make sure func has an open websocket client
    """
    ws = call.app.config.websocket_client
    if ws and ws.open:
        # everything ok, noop
        pass
    else:
        ws = await websockets.connect(**call.app.config.websocket_kwargs)
        call.app.config.websocket_client = ws
    return await call()


@decorator
async def ignore_errors_async(call: Callable) -> Callable:
    try:
        # pylint: disable=protected-access
        if not asyncio.iscoroutinefunction(call._func):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            return await loop.run_in_executor(executor, func=call)
        return await call()
    except Exception as e:
        logger.error('Error ignored %s', e)


def async_exclude_methods(middleware_func: Optional[Callable]=None,
                          exclude_http_methods: Tuple[str]=None):
    """Exclude specified HTTP methods from middleware

    Args:
        middleware_func:
        exclude_http_methods:

    Returns:

    """
    if middleware_func is None:
        return functools.partial(
            async_exclude_methods, exclude_http_methods=exclude_http_methods)

    @functools.wraps(middleware_func)
    async def f(request: HTTPRequest) -> Union[None, HTTPResponse]:
        if request.method in exclude_http_methods:
            return
        return await middleware_func(request)

    return f


@decorator
async def return_bytes(call: Callable) -> Callable:
    """Decorate func to make sure func has an open websocket client
    """
    result = await call()
    if isinstance(result, str):
        result = result.encode()
    return result


@apply_single_or_batch
def sort_request(
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> OrderedDict:
    params = single_jsonrpc_request.get('params')
    if isinstance(params, list):
        single_jsonrpc_request['params'] = sorted(params)
    elif isinstance(params, dict):
        single_jsonrpc_request['params'] = OrderedDict(
            sorted(single_jsonrpc_request['params']))
    return OrderedDict(sorted(single_jsonrpc_request.items()))


@apply_single_or_batch
def is_valid_jsonrpc_request(
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> None:
    assert single_jsonrpc_request.get('jsonrpc') == '2.0'
    assert isinstance(single_jsonrpc_request.get('method'), str)
    if 'id' in single_jsonrpc_request:
        assert isinstance(single_jsonrpc_request['id'], (int, str, type(None)))
    if 'params' in single_jsonrpc_request:
        assert isinstance(single_jsonrpc_request, (list, dict))


def parse_namespaced_method(namespaced_method: str,
                            default_namespace: str='steemd'
                            ) -> Tuple[str, str]:
    parts = namespaced_method.split('.')
    if len(parts) == 1:
        return default_namespace, namespaced_method
    return parts[0], '.'.join(parts[1:])


async def get_upstream(
    sanic_http_request: HTTPRequest,
    single_jsonrpc_request: SingleJsonRpcRequest) -> Tuple[str, int]:
    app = sanic_http_request.app
    jsonrpc_method = single_jsonrpc_request['method']
    _, upstream = app.config.upstreams.longest_prefix(jsonrpc_method)

    # get default values if no specific values found
    if upstream is None:
        _, upstream = app.config.upstreams.longest_prefix('')

    return upstream['url'], upstream['ttl']


async def jussi_attrs(sanic_http_request: HTTPRequest) -> HTTPRequest:
    from jussi.cache import jsonrpc_cache_key
    jsonrpc_requests = sanic_http_request.json

    app = sanic_http_request.app

    if isinstance(jsonrpc_requests, list):
        results = []
        for i, r in enumerate(jsonrpc_requests):
            if not r:
                raise InvalidUsage('Bad jsonrpc request')
            key = jsonrpc_cache_key(r)
            url, ttl = await get_upstream(sanic_http_request, r)
            cacheable = ttl > app.config.cache_config['no_cache_ttl']
            is_ws = url.startswith('ws')
            namespace, method_name = parse_namespaced_method(r['method'])
            prefix = '.'.join([str(i), namespace, method_name])
            results.append(
                JussiAttrs(
                    key=key,
                    upstream_url=url,
                    ttl=ttl,
                    cacheable=cacheable,
                    is_ws=is_ws,
                    namespace=namespace,
                    method_name=method_name,
                    log_prefix=prefix))
        sanic_http_request['jussi'] = results
        sanic_http_request['jussi_is_batch'] = True
    else:
        key = jsonrpc_cache_key(jsonrpc_requests)
        url, ttl = await get_upstream(sanic_http_request, jsonrpc_requests)
        cacheable = ttl > app.config.cache_config['no_cache_ttl']
        is_ws = url.startswith('ws')
        namespace, method_name = parse_namespaced_method(
            jsonrpc_requests['method'])
        prefix = '.'.join(['0', namespace, method_name])
        sanic_http_request['jussi'] = JussiAttrs(
            key=key,
            upstream_url=url,
            ttl=ttl,
            cacheable=cacheable,
            is_ws=is_ws,
            namespace=namespace,
            method_name=method_name,
            log_prefix=prefix)
        sanic_http_request['jussi_is_batch'] = False

    return sanic_http_request
