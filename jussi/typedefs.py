# -*- coding: utf-8 -*-
from typing import Dict
from typing import List
from typing import TypeVar
from typing import Union

import pygtrie
from sanic.app import Sanic
from sanic.response import HTTPResponse as SanicHTTPResponse

from jussi.request.http import HTTPRequest
from jussi.request.jsonrpc import JSONRPCRequest

WebApp = Sanic
HTTPRequest = HTTPRequest
HTTPResponse = SanicHTTPResponse

# JSONRPC Request/Response fields
JrpcRequestIdField = TypeVar('JRPCIdField', str, int, float, type(None))
JrpcRequestParamsField = TypeVar('JRPCParamsField', type(None), list, dict)
JrpcRequestVersionField = str
JrpcRequestMethodField = str
JrpcField = TypeVar('JrpcField',
                    JrpcRequestIdField,
                    JrpcRequestParamsField,
                    JrpcRequestVersionField,
                    JrpcRequestMethodField)
JrpcResponseField = TypeVar('JrpcResponseField', str, int, float, type(None), bool, list, dict)

# JSONRPC Requests
SingleRawRequest = Dict[str, JrpcField]
BatchRawRequest = List[SingleRawRequest]
RawRequest = TypeVar('RawRequest', SingleRawRequest, BatchRawRequest)


SingleJrpcRequest = JSONRPCRequest
BatchJrpcRequest = List[SingleJrpcRequest]
JrpcRequest = TypeVar('JrpcRequest', SingleJrpcRequest,
                      BatchJrpcRequest)

# JSONRPC Responses
SingleJrpcResponse = Dict[str, JrpcResponseField]
BatchJrpcResponse = List[SingleJrpcResponse]
JrpcResponse = TypeVar('JrpcResponse', SingleJrpcResponse,
                       BatchJrpcResponse)

# Cached JSONRPC Responses
CachedSingleResponse = SingleJrpcResponse
CachedBatchResponse = List[Union[None, CachedSingleResponse]]
CachedResponse = TypeVar('CachedResponse', CachedSingleResponse,
                         CachedBatchResponse)

StringTrie = pygtrie.StringTrie


def urn_type():
    from .urn import URN
    return URN


def upstreams_type():
    from .upstream import _Upstreams
    return _Upstreams


def upstream_type():
    from .upstream import Upstream
    return Upstream


#URN = urn_type()
#Upstream = upstream_type()
#Upstreams = upstreams_type()
