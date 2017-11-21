# -*- coding: utf-8 -*-
import logging
from collections import namedtuple
from typing import Tuple
from typing import Union

from ..typedefs import JsonRpcRequest
from ..typedefs import SingleJsonRpcRequest

logger = logging.getLogger(__name__)

URNParts = namedtuple('URNParts', ['namespace', 'api', 'method', 'params'])

NAMESPACES = frozenset(
    ['hivemind', 'jussi', 'overseer', 'sbds', 'steemd', 'yo'])


def parse_namespaced_method(namespaced_method: str,
                            default_namespace: str='steemd',
                            namespaces: frozenset=NAMESPACES
                            ) -> Tuple[str, str]:
    parts = namespaced_method.split('.', maxsplit=1)
    if len(parts) == 0:
        raise ValueError(
            f'{namespaced_method} is an invalid namespaced method')
    if len(parts) == 1:
        return default_namespace, namespaced_method
    if parts[0] not in namespaces:
        raise ValueError(f'{parts[0]} is an invalid namespace')
    return parts[0], parts[1]


def urn(single_jsonrpc_request: SingleJsonRpcRequest) -> str:
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


def urn_parts(single_jsonrpc_request: SingleJsonRpcRequest) -> URNParts:
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
    return URNParts(namespace, api, method, params)


def x_jussi_urn_parts(request: JsonRpcRequest) -> Union[URNParts, str]:
    try:
        if isinstance(request, dict):
            parts = urn_parts(request)
            params = limit_len(parts.params)
            return URNParts(parts.namespace, parts.api, parts.method, params)
        elif isinstance(request, list):
            return 'batch'
        return 'null'
    except BaseException:
        return 'null'


def limit_len(item, maxlen=100):
    if isinstance(item, (list, tuple)):
        return [limit_len(i, maxlen=maxlen) for i in item]
    elif isinstance(item, dict):
        return {k: limit_len(v, maxlen=maxlen) for k, v in item.items()}
    elif isinstance(item, str):
        if len(item) > maxlen:
            return ''.join([item[:maxlen], '...'])
        else:
            return item
    else:
        return item


def stringify(items):
    return f'{items}'.replace(' ', '')
