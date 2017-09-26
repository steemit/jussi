# -*- coding: utf-8 -*-
import functools
import logging
from collections import OrderedDict
from collections import namedtuple
from copy import deepcopy
from typing import Callable
from typing import Optional
from typing import Tuple

from funcy.decorators import Call
from funcy.decorators import decorator



from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcRequest
from .typedefs import SingleJsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .typedefs import StringTrie

logger = logging.getLogger(__name__)

JSONRPC_REQUEST_KEYS = {'id', 'jsonrpc', 'method', 'params'}

JussiJRPC = namedtuple('JussiJRPC', ['namespace', 'api', 'method', 'params'])

# decorators


@decorator
def apply_single_or_batch(call: Call) -> JsonRpcRequest:
    """Decorate func to apply func to single or batch jsonrpc_requests
    """
    if isinstance(call.single_jsonrpc_request, list):
        original = deepcopy(call.single_jsonrpc_request)
        results = []
        for request in original:
            # pylint: disable=protected-access
            call._kwargs['single_jsonrpc_request'] = request
            results.append(call())
        return results
    return call()


def async_exclude_methods(
        middleware_func: Optional[Callable]=None,
        exclude_http_methods: Tuple[str]=None) -> Optional[Callable]:
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
    async def f(request: HTTPRequest) -> Optional[HTTPResponse]:
        if request.method in exclude_http_methods:
            return
        return await middleware_func(request)

    return f


@apply_single_or_batch
def sort_request(
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> OrderedDict:
    params = single_jsonrpc_request.get('params')
    if isinstance(params, dict):
        single_jsonrpc_request['params'] = dict(
            sorted(single_jsonrpc_request['params'].items()))
    return OrderedDict(sorted(single_jsonrpc_request.items()))


@apply_single_or_batch
def is_valid_jsonrpc_request(
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> None:
    if not isinstance(single_jsonrpc_request, dict):
        raise ValueError('Not JSONRPC Request')
    assert JSONRPC_REQUEST_KEYS.issuperset(single_jsonrpc_request.keys())
    assert single_jsonrpc_request.get('jsonrpc') == '2.0'
    assert isinstance(single_jsonrpc_request.get('method'), str)
    if 'id' in single_jsonrpc_request:
        assert isinstance(single_jsonrpc_request['id'], (int, str, type(None)))


def parse_namespaced_method(namespaced_method: str,
                            default_namespace: str='steemd'
                            ) -> Tuple[str, str]:
    parts = namespaced_method.split('.')
    if len(parts) == 1:
        return default_namespace, namespaced_method
    return parts[0], '.'.join(parts[1:])


def method_urn(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    api = None
    query = ''
    namespace, method = parse_namespaced_method(
        single_jsonrpc_request['method'])
    params = single_jsonrpc_request.get('params', None)
    if isinstance(params, dict):
        params = dict(sorted(params.items()))
    if namespace == 'steemd':
        if method == 'call':
            assert isinstance(params, list)
            api = params[0]
            method = params[1]
            params = params[2]
        else:
            api = 'database_api'
    if params and params != []:
        query = f'.params={params}'.replace(' ', '')
    return '.'.join([p for p in (
        namespace,
        api,
        method, ) if p]) + query


def method_urn_parts(single_jsonrpc_request: SingleJsonRpcRequest) -> tuple:
    api = None
    namespace, method = parse_namespaced_method(
        single_jsonrpc_request['method'])
    params = single_jsonrpc_request.get('params', None)
    if isinstance(params, dict):
        params = dict(sorted(params.items()))
    if namespace == 'steemd':
        if method == 'call':
            api = params[0]
            method = params[1]
            params = params[2]
        else:
            api = 'database_api'
    return JussiJRPC(namespace, api, method, params)


def stats_key(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
    api = None
    namespace, method = parse_namespaced_method(
        single_jsonrpc_request['method'])
    params = single_jsonrpc_request.get('params', None)
    if isinstance(params, dict):
        params = dict(sorted(params.items()))
    if namespace == 'steemd':
        if method == 'call':
            assert isinstance(params, list)
            api = params[0]
            method = params[1]
            params = params[2]
        else:
            api = 'database_api'
    return '.'.join([p for p in (
        namespace,
        api,
        method, ) if p])


def get_upstream(upstreams, single_jsonrpc_request: SingleJsonRpcRequest
                 ) -> Tuple[str, int]:
    urn = method_urn(single_jsonrpc_request)
    _, ttl = upstreams.longest_prefix(urn)
    return 'error', ttl


def is_batch_jsonrpc(
        jsonrpc_request: JsonRpcRequest=None,
        sanic_http_request: HTTPRequest=None, ) -> bool:
    try:
        return isinstance(jsonrpc_request, list) or isinstance(
            sanic_http_request.json, list)
    except Exception as e:
        logger.debug(f'is_batch_response exception:{e}')
        return False


def is_jsonrpc_error_response(jsonrpc_response: SingleJsonRpcResponse) -> bool:
    try:
        if not jsonrpc_response:
            return True
        if not isinstance(jsonrpc_response, dict):
            return True
        if 'error' in jsonrpc_response:
            return True
    except Exception as e:
        logger.debug(f'is_jsonrpc_error_response exception:{e}')

    return False


def upstream_url_from_jsonrpc_request(
        upstream_urls: StringTrie=None,
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> str:
    urn = method_urn(single_jsonrpc_request=single_jsonrpc_request)
    return upstream_url_from_urn(upstream_urls, urn=urn)


def upstream_url_from_urn(upstream_urls: StringTrie=None,
                          urn: str=None) -> str:
    _, url = upstream_urls.longest_prefix(urn)
    return url
