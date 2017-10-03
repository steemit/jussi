# -*- coding: utf-8 -*-
import logging
from collections import namedtuple
from typing import Tuple

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
