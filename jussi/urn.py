# -*- coding: utf-8 -*-

import logging
import reprlib
from collections import namedtuple
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

logger = logging.getLogger(__name__)


NAMESPACES = frozenset(
    ['hivemind', 'jussi', 'overseer', 'sbds', 'steemd', 'yo'])


def parse_namespaced_method(namespaced_method: str,
                            default_namespace: str = 'steemd'):
    parts = namespaced_method.split('.', maxsplit=1)
    if parts[0] not in NAMESPACES:
        return default_namespace, namespaced_method
    return parts[0], parts[1]


class URN(namedtuple('URN', 'namespace api method params')):
    @classmethod
    def from_request(cls, single_jsonrpc_request: dict) -> namedtuple:
        return cls(*cls.__parts(single_jsonrpc_request))

    # pylint: disable=no-member
    @staticmethod
    def __parts(single_jsonrpc_request: dict) -> Tuple:
        api = None
        namespace, method = parse_namespaced_method(
            single_jsonrpc_request['method'])
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


def x_jussi_urn_parts(request: Union[List[Dict[str, any]], Dict[str, any]]) -> Union[URN, str]:
    try:
        if isinstance(request, dict):
            parts = URN.from_request(request)
            params = stringify(limit_len(parts.params))

            return URN(parts.namespace, parts.api, parts.method, params)
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
