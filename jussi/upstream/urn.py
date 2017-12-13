# -*- coding: utf-8 -*-
import logging
from collections import namedtuple
from typing import Tuple
from typing import Union

from ..errors import InvalidNamespaceError
from ..typedefs import JsonRpcRequest
from ..typedefs import SingleJsonRpcRequest

logger = logging.getLogger(__name__)

URNParts = namedtuple('URNParts', ['namespace', 'api', 'method', 'params'])

NAMESPACES = frozenset(
    ['hivemind', 'jussi', 'overseer', 'sbds', 'steemd', 'yo'])

APPBASE_APIS = frozenset((
    'account_by_key_api',
    'account_by_key_api',
    'account_history_api',
    'block_api',
    'chain_api',
    'condenser_api',
    'database_api',
    'debug_node_api',
    'follow_api',
    'market_history_api',
    'network_broadcast_api',
    'tags_api',
    'test_api',
    'witness_api'
))

COMBINED_NAMESPACES = NAMESPACES.union(APPBASE_APIS)


def parse_namespaced_method(namespaced_method: str,
                            default_namespace: str='steemd',
                            namespaces: frozenset=COMBINED_NAMESPACES,
                            steemd_apis: frozenset=APPBASE_APIS
                            ) -> Tuple[str, str]:
    parts = namespaced_method.split('.', maxsplit=1)
    if len(parts) == 0:
        raise InvalidNamespaceError(namespace=namespaced_method)
    if len(parts) == 1:
        return default_namespace, namespaced_method
    if parts[0] in steemd_apis:
        return default_namespace, namespaced_method
    if parts[0] not in namespaces:
        raise InvalidNamespaceError(namespace=namespaced_method)
    return parts[0], parts[1]

# pylint: disable=no-member


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
            if len(params) > 2:
                params = params[2]
            else:
                params = None
        else:
            method_parts = method.split('.')
            if len(method_parts) == 1:
                api = 'database_api'
            if len(method_parts) == 2:
                api = method_parts[0]
                method = method_parts[1]
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
            if len(params) > 2:
                params = params[2]
        else:
            method_parts = method.split('.')
            if len(method_parts) == 1:
                api = 'database_api'
            if len(method_parts) == 2:
                api = method_parts[0]
                method = method_parts[1]
    return URNParts(namespace, api, method, params)


def x_jussi_urn_parts(request: JsonRpcRequest) -> Union[URNParts, str]:
    try:
        if isinstance(request, dict):
            parts = urn_parts(request)
            params = stringify(limit_len(parts.params))

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


def stringify(items, maxlen=1000):
    return f'{items}'.replace(' ', '')[:maxlen]
