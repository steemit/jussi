# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Union
from typing import TypeVar

import pygtrie
from sanic.app import Sanic

from sanic.response import HTTPResponse as SanicHTTPResponse

from jussi.request import HTTPRequest
from jussi.request import JSONRPCRequest

WebApp = Sanic
HTTPRequest = HTTPRequest
HTTPResponse = SanicHTTPResponse

# JSONRPC Request fields
JsonRpcRequestIdField = TypeVar('JRPCIdField', str, int, float, None)
JsonRpcRequestParamsField = TypeVar('JRPCParamsField', None, list, dict)
JsonRpcRequestVersionField = str
JsonRpcRequestMethodField = str

# JSONRPC Requests
RawRequestDict = Dict[str, Union[str, float, int, list, dict]]
RawRequestList = List[RawRequestDict]
RawRequest = TypeVar('RawRequest', RawRequestDict, RawRequestList)


SingleJsonRpcRequest = JSONRPCRequest
BatchJsonRpcRequest = List[SingleJsonRpcRequest]
JsonRpcRequest = TypeVar('JsonRpcRequest', SingleJsonRpcRequest,
                         BatchJsonRpcRequest)

# JSONRPC Responses
JsonRpcResponseDict = Dict[str, Any]
SingleJsonRpcResponse = Dict[str, Any]
BatchJsonRpcResponse = List[SingleJsonRpcResponse]
JsonRpcResponse = TypeVar('JsonRpcResponse', SingleJsonRpcResponse,
                          BatchJsonRpcResponse)

# Cached JSONRPC Responses
CachedSingleResponse = SingleJsonRpcResponse
CachedBatchResponse = List[Union[None, CachedSingleResponse]]
CachedResponse = TypeVar('CachedResponse', CachedSingleResponse,
                         CachedBatchResponse)

StringTrie = pygtrie.StringTrie
