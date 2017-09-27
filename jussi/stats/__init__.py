# -*- coding: utf-8 -*-
from ..typedefs import SingleJsonRpcRequest
from ..upstream.urn import parse_namespaced_method


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
