# -*- coding: utf-8 -*-
from random import getrandbits
from time import perf_counter
from typing import Dict
from typing import List
from typing import Optional
from typing import TypeVar
from typing import Union
from urllib.parse import urlunparse

# pylint: disable=no-name-in-module
from httptools import parse_url
from ujson import loads as json_loads

from jussi.empty import _empty
from jussi.request.jsonrpc import JSONRPCRequest
from jussi.request.jsonrpc import from_http_request as jsonrpc_from_request

# pylint: enable=no-name-in-module


# HTTP/1.1: https://www.w3.org/Protocols/rfc2616/rfc2616-sec7.html#sec7.2.1
# > If the media type remains unknown, the recipient SHOULD treat it
# > as type "application/octet-stream"
DEFAULT_HTTP_CONTENT_TYPE = "application/json"


RawRequestDict = Dict[str, Union[str, float, int, list, dict, bool, type(None)]]
RawRequestList = List[RawRequestDict]
RawRequest = TypeVar('RawRequest', RawRequestDict, RawRequestList)

SingleJrpcRequest = JSONRPCRequest
BatchJrpcRequest = List[SingleJrpcRequest]
JrpcRequest = TypeVar('JrpcRequest', SingleJrpcRequest,
                      BatchJrpcRequest)

# pylint: disable=too-many-instance-attributes,too-many-arguments,attribute-defined-outside-init


class HTTPRequest:
    """HTTP request optimized for use in JSONRPC reverse proxy"""

    __slots__ = (
        'app', 'headers', 'version', 'method', 'transport',
        'body', '_parsed_json', '_parsed_jsonrpc',
        '_ip', '_parsed_url', 'uri_template', 'stream',
        '_socket', '_port', 'timings', '_log', 'is_batch_jrpc',
        'is_single_jrpc'
    )

    def __init__(self, url_bytes: bytes, headers: dict,
                 version: str, method: str, transport) -> None:
        self._parsed_url = parse_url(url_bytes)
        self.app = None

        self.headers = headers
        self.version = version
        self.method = method
        self.transport = transport

        # Init but do not inhale
        self.body = []
        self._parsed_json = _empty
        self._parsed_jsonrpc = _empty
        self.uri_template = None
        self.stream = None
        self.is_batch_jrpc = False
        self.is_single_jrpc = False

        self.timings = [(perf_counter(), 'http_create')]
        self._log = _empty

    @property
    def jsonrpc(self) -> Optional[JrpcRequest]:
        # ignore body and json if HTTP methos is not POST
        if self.method != 'POST':
            return None

        if self._parsed_jsonrpc is _empty:
            self._parsed_jsonrpc = None
            from jussi.errors import ParseError
            from jussi.errors import InvalidRequest
            from jussi.validators import validate_jsonrpc_request
            try:
                # raise ParseError for blank/empty body
                if self.body is _empty:
                    raise ParseError(http_request=self)
                # raise ParseError if parsing fails
                try:
                    self._parsed_json = json_loads(self.body)
                except Exception as e:
                    raise ParseError(http_request=self, exception=e)

                # validate jsonrpc
                jsonrpc_request = self._parsed_json
                validate_jsonrpc_request(jsonrpc_request)

                if isinstance(jsonrpc_request, dict):
                    self._parsed_jsonrpc = jsonrpc_from_request(self, 0,
                                                                jsonrpc_request)
                    self.is_single_jrpc = True
                elif isinstance(jsonrpc_request, list):
                    self._parsed_jsonrpc = [
                        jsonrpc_from_request(self, batch_index, req)
                        for batch_index, req in enumerate(jsonrpc_request)
                    ]
                    self.is_batch_jrpc = True
            except ParseError as e:
                raise e
            except Exception as e:
                raise InvalidRequest(http_request=self, exception=e)
        return self._parsed_jsonrpc

    @property
    def ip(self):
        if not hasattr(self, '_socket'):
            self._get_address()
        return self._ip

    @property
    def port(self):
        if not hasattr(self, '_socket'):
            self._get_address()
        return self._port

    @property
    def socket(self):
        return None

    def _get_address(self):
        try:
            self._socket = (self.transport.get_extra_info('peername') or
                            (None, None))
            self._ip, self._port = self._socket
        except Exception:
            self._ip, self._port = None, None

    @property
    def scheme(self):
        scheme = 'http'
        try:
            if self.transport.get_extra_info('sslcontext'):
                scheme += 's'
        except Exception:
            pass
        return scheme

    @property
    def host(self):
        # it appears that httptools doesn't return the host
        # so pull it from the headers
        return self.headers.get('Host', '')

    @property
    def content_type(self):
        return self.headers.get('Content-Type', DEFAULT_HTTP_CONTENT_TYPE)

    @property
    def match_info(self):
        """return matched info after resolving route"""
        return self.app.router.get(self)[2]

    @property
    def path(self) -> str:
        return self._parsed_url.path.decode('utf-8')

    @property
    def query_string(self):
        if self._parsed_url.query:
            return self._parsed_url.query.decode('utf-8')
        else:
            return ''

    @property
    def url(self):
        return urlunparse((
            self.scheme,
            self.host,
            self.path,
            None,
            self.query_string,
            None))

    @property
    def jussi_request_id(self) -> str:
        return self.headers.get('x-jussi-request-id',
                                '%(rid)018d' % {'rid': getrandbits(50)})

    @property
    def amzn_trace_id(self) -> str:
        return self.headers.get('x-amzn-trace-id', '')

    @property
    def request_start_time(self) -> float:
        return self.timings[0][0]

    @property
    def request_timeout(self) -> Union[int, float]:
        if self.is_single_jrpc:
            return self.jsonrpc.upstream.timeout
        elif self.is_batch_jrpc:
            return min([sum(r.upstream.timeout for r in self.jsonrpc), 60])
        else:
            return 1
