# -*- coding: utf-8 -*-
from typing import Dict
from typing import List
from typing import Union

import pygtrie
from sanic.app import Sanic
from sanic.request import Request
from sanic.response import HTTPResponse as SanicHTTPResponse

WebApp = Sanic
HTTPRequest = Request
HTTPResponse = SanicHTTPResponse

# JSONRPC Requests
SingleJsonRpcRequest = Dict[str, Union[str,int,float, None,list,dict]]
BatchJsonRpcRequest = List[SingleJsonRpcRequest]
JsonRpcRequest = Union[SingleJsonRpcRequest, BatchJsonRpcRequest]

# JSONRPC Responses
SingleJsonRpcResponse = Dict[str, Union[str,int,float, None,list,dict]]
BatchJsonRpcResponse = List[SingleJsonRpcResponse]
JsonRpcResponse = Union[SingleJsonRpcRequest, BatchJsonRpcRequest]

# Cached JSONRPC Responses
CachedSingleResponse = SingleJsonRpcResponse
CachedBatchResponse = List[Union[None,CachedSingleResponse]]
CachedResponse = Union[CachedSingleResponse,CachedBatchResponse]

StringTrie = pygtrie.StringTrie
