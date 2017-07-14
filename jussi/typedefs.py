# -*- coding: utf-8 -*-

from typing import Dict
from typing import List
from typing import NamedTuple
from typing import Union

from sanic.app import Sanic
from sanic.request import Request
from sanic.response import HTTPResponse as SanicHTTPResponse

WebApp = Sanic
HTTPRequest = Request
HTTPResponse = SanicHTTPResponse
JsonRpcRequest = Union[Dict, List]
SingleJsonRpcRequest = Dict


# pylint: disable=too-few-public-methods
class JussiAttrs(NamedTuple):
    key: str
    upstream_url: str
    ttl: int
    cacheable: bool
    is_ws: bool
    namespace: str
    method_name: str
    log_prefix: str
