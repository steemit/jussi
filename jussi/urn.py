# -*- coding: utf-8 -*-
import functools
import re
import reprlib
from collections import namedtuple

import structlog

from .errors import InvalidNamespaceAPIError
from .errors import InvalidNamespaceError

logger = structlog.get_logger(__name__)

JRPC_METHOD_PATTERN = r'(^(?P<appbase_api>[^\.]+_api)\.(?P<appbase_method>[^\.]+)$)|^(?P<bare_method>^[^\.]+)$|^(?P<namespace>[^\.]+){1}\.(?:(?P<api>[^\.]+)\.){0,1}(?P<method>[^\.]+){1}$'
JRPC_METHOD_REGEX = re.compile(JRPC_METHOD_PATTERN)


STEEMD_NUMERIC_API_MAPPING = ('database_api', 'login_api')


class URN(namedtuple('URN', 'namespace api method params')):
    __cached_str = None

    @classmethod
    def from_request(cls, single_jsonrpc_request: dict) -> namedtuple:
        parsed = cls._parse_jrpc(single_jsonrpc_request)
        if isinstance(parsed['params'], dict):
            parsed['params'] = dict(sorted(parsed['params'].items()))

        return cls(namespace=parsed['namespace'],
                   api=parsed['api'],
                   method=parsed['method'],
                   params=parsed['params'])

    # pylint: disable=no-member

    @staticmethod
    @functools.lru_cache(8192)
    def _parse_jrpc_method(jrpc_method: str) -> dict:
        return JRPC_METHOD_REGEX.match(jrpc_method).groupdict(default=False)

    # pylint: disable=too-many-branches
    @staticmethod
    def _parse_jrpc(single_jsonrpc_request: dict):
        try:
            method = single_jsonrpc_request['method']
            params = single_jsonrpc_request.get('params', False)

            matched = URN._parse_jrpc_method(method)

            if matched.get('appbase_api'):
                return {
                    'namespace': 'appbase',
                    'api': matched['appbase_api'],
                    'method': matched['appbase_method'],
                    'params': params
                }
            if matched.get('namespace'):
                if matched['namespace'] == 'jsonrpc':
                    return {
                        'namespace': 'appbase',
                        'api': 'jsonrpc',
                        'method': matched['method'],
                        'params': params
                    }
                return {
                    'namespace': matched['namespace'],
                    'api': matched.get('api'),
                    'method': matched['method'],
                    'params': params
                }
            if matched['bare_method']:
                method = matched['bare_method']

                if method != 'call':
                    return {
                        'namespace': 'steemd',
                        'api': 'database_api',
                        'method': method,
                        'params': params
                    }

                if len(params) != 3:
                    namespace = 'appbase'
                    api, method = params
                    _params = False
                else:
                    api, method, _params = params
                    if api == 'condenser_api' or isinstance(_params, dict) or api == 'jsonrpc':
                        namespace = 'appbase'
                    else:
                        namespace = 'steemd'
                if isinstance(api, int):
                    try:
                        api = STEEMD_NUMERIC_API_MAPPING[api]
                    except IndexError:
                        raise InvalidNamespaceAPIError(namespace='steemd',
                                                       api=api)

                return {
                    'namespace': namespace,
                    'api': api,
                    'method': method,
                    'params': _params
                }
            else:
                logger.error('failed to parse request method', extra={'matched': matched,
                                                                      'params': params})
                raise InvalidNamespaceError(namespace=single_jsonrpc_request['method'])
        except InvalidNamespaceAPIError as e:
            raise e
        except InvalidNamespaceError as e:
            raise e
        except Exception as e:
            raise InvalidNamespaceError(namespace=single_jsonrpc_request['method'])
    # pylint: enable=too-many-branches

    def __repr__(self):
        return f'URN(namespace={self.namespace}, api={self.api}, method={self.method}, params={reprlib.repr(self.params)})'

    def __str__(self):
        if self.__cached_str:
            return self.__cached_str
        params = self.params
        if self.params is not False:
            params = f'params={self.params}'.replace(' ', '')

        api = self.api
        if api is not False:
            api = str(self.api)
        self.__cached_str = '.'.join(
            p for p in (
                self.namespace,
                api,
                self.method,
                params) if p is not False)
        return self.__cached_str

    def __hash__(self):
        return hash(str(self))

    def __eq__(self, urn):
        return hash(urn) == hash(self)
