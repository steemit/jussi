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


SingleJsonRpcRequest = Dict
BatchJsonRpcRequest = List[SingleJsonRpcRequest]
JsonRpcRequest = Union[SingleJsonRpcRequest, BatchJsonRpcRequest]
StringTrie = pygtrie.StringTrie
