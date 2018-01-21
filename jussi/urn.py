# -*- coding: utf-8 -*-

import logging
import reprlib
from collections import namedtuple
from typing import Tuple

logger = logging.getLogger(__name__)


def parse_namespaced_method(namespaced_method: str=None,
                            namespaces: frozenset=None,
                            default_namespace: str = 'steemd'):
    parts = namespaced_method.split('.', maxsplit=1)
    if parts[0] not in namespaces:
        return default_namespace, namespaced_method
    return parts[0], parts[1]


class URN(namedtuple('URN', 'namespace api method params')):
    @classmethod
    def from_request(cls, single_jsonrpc_request: dict,
                     namespaces: frozenset=None) -> namedtuple:
        return cls(*cls.__parts(single_jsonrpc_request, namespaces))

    # pylint: disable=no-member
    @staticmethod
    def __parts(single_jsonrpc_request: dict=None,
                namespaces: frozenset=None) -> Tuple:
        api = None
        namespace, method = parse_namespaced_method(
            namespaced_method=single_jsonrpc_request['method'],
            namespaces=namespaces)
        params = single_jsonrpc_request.get('params', None)
        if namespace == 'steemd':
            if method == 'call':
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
        if isinstance(params, dict):
            params = dict(sorted(params.items()))
        return namespace, api, method, params
    # pylint: enable=no-member

    @property
    def parts(self):
        return self

    def __repr__(self):
        return f'URN(namespace={self.namespace}, api={self.api}, method={self.method}, params={reprlib.repr(self.params)})'

    def __str__(self):
        if self.params:
            params = f'params={self.params}'.replace(' ', '')
        else:
            params = self.params
        return '.'.join(p for p in (self.namespace, self.api, self.method, params) if p)

    def __hash__(self):
        return hash(str(self))
