# -*- coding: utf-8 -*-
from typing import Any
from typing import Dict
from typing import List
from typing import Union

import pygtrie
from sanic.app import Sanic
from sanic.request import Request
from sanic.response import HTTPResponse as SanicHTTPResponse

from .request import JussiJSONRPCRequest

WebApp = Sanic
HTTPRequest = Request
HTTPResponse = SanicHTTPResponse

# JSONRPC Request fields
JsonRpcRequestIdField = Union[str, float, None]
JsonRpcRequestParamsField = Union[str, int, float, None, list, dict]
JsonRpcRequestVersionField = str
JsonRpcRequestMethodField = str

# JSONRPC Requests
JsonRpcRequestDict = Dict[str, Any]
SingleJsonRpcRequest = JussiJSONRPCRequest  # Dict[str, Any]
BatchJsonRpcRequest = List[SingleJsonRpcRequest]
JsonRpcRequest = Union[SingleJsonRpcRequest, BatchJsonRpcRequest]

# JSONRPC Responses
JsonRpcResponseDict = Dict[str, Any]
SingleJsonRpcResponse = Dict[str, Any]
BatchJsonRpcResponse = List[SingleJsonRpcResponse]
JsonRpcResponse = Union[SingleJsonRpcResponse, BatchJsonRpcResponse]

# JSONRPC Errors
JsonRpcErrorObject = Dict[str, Union[int, str, dict]]
JsonRpcErrorResponse = Dict[str, Any]

# Cached JSONRPC Responses
CachedSingleResponse = SingleJsonRpcResponse
CachedBatchResponse = List[Union[None, CachedSingleResponse]]
CachedResponse = Union[CachedSingleResponse, CachedBatchResponse]

StringTrie = pygtrie.StringTrie
