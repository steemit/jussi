# -*- coding: utf-8 -*-
import logging
from typing import Optional

from sanic import response
from sanic.exceptions import InvalidUsage

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from ..errors import InvalidRequest
from ..errors import ParseError
from ..errors import ServerError
from ..errors import handle_middleware_exceptions
from ..upstream import async_exclude_methods
from ..upstream import is_valid_jsonrpc_request
from ..upstream import sort_request

logger = logging.getLogger(__name__)


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def validate_jsonrpc_request(
        request: HTTPRequest) -> Optional[HTTPResponse]:
    try:
        is_valid_jsonrpc_request(single_jsonrpc_request=request.json)
        request.parsed_json = sort_request(single_jsonrpc_request=request.json)
        request['sorted_json'] = sort_request(
            single_jsonrpc_request=request.json)
    except AssertionError as e:
        # invalid jsonrpc
        return response.json(
            InvalidRequest(sanic_request=request, exception=e).to_dict())
    except (InvalidUsage, ValueError) as e:
        return response.json(
            ParseError(sanic_request=request, exception=e).to_dict())
    except Exception as e:
        # json failed to parse
        return response.json(
            ServerError(sanic_request=request, exception=e).to_dict())
