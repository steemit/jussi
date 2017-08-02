# -*- coding: utf-8 -*-
import asyncio
import functools
import logging
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from typing import Callable
from typing import Optional
from typing import Tuple

from funcy.decorators import Call
from funcy.decorators import decorator

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcRequest
from jussi.typedefs import SingleJsonRpcRequest
from jussi.typedefs import StringTrie
from jussi.typedefs import WebApp

logger = logging.getLogger('sanic')

JSONRPC_REQUEST_KEYS = set(['id','jsonrpc','method','params'])

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


@decorator
async def ignore_errors_async(call: Call) -> Optional[dict]:
    try:
        # pylint: disable=protected-access
        if not asyncio.iscoroutinefunction(call._func):
            loop = asyncio.get_event_loop()
            executor = ThreadPoolExecutor(max_workers=1)
            return await loop.run_in_executor(executor, call)
        return await call()
    except Exception as e:
        logger.exception('Error ignored %s', e)


def async_exclude_methods(middleware_func: Optional[Callable]=None,
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
        query = ('.params=%s' % params).replace(' ', '')
    return '.'.join([p for p in (namespace, api, method, ) if p]) + query


def get_upstream(upstreams, single_jsonrpc_request: SingleJsonRpcRequest
                 ) -> Tuple[str, int]:
    urn = method_urn(single_jsonrpc_request)
    _, ttl = upstreams.longest_prefix(urn)
    return 'error', ttl


def is_batch_jsonrpc(
        jsonrpc_request: JsonRpcRequest=None,
        sanic_http_request: HTTPRequest=None, ) -> bool:
    return isinstance(jsonrpc_request, list) or isinstance(
        sanic_http_request.json, list)


def upstream_url_from_jsonrpc_request(
        upstream_urls: StringTrie=None,
        single_jsonrpc_request: SingleJsonRpcRequest=None) -> str:
    urn = method_urn(single_jsonrpc_request=single_jsonrpc_request)
    return upstream_url_from_urn(upstream_urls, urn=urn)


def upstream_url_from_urn(upstream_urls: StringTrie=None,
                          urn: str=None) -> str:
    _, url = upstream_urls.longest_prefix(urn)
    return url


# pylint: disable=super-init-not-called
class AttrDict(dict):
    def __init__(self, *args, **kwargs) -> None:
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class DummyRequest(AttrDict):
    def __init__(self, app: WebApp=None, json: dict=None) -> None:
        self.app = app
        self.json = json
