# -*- coding: utf-8 -*-
from typing import Optional

import structlog
from sanic import response
from sanic.exceptions import InvalidUsage

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from ..errors import JsonRpcError
from ..errors import InvalidRequest
from ..errors import ParseError
from ..errors import ServerError

from ..errors import handle_middleware_exceptions
from ..utils import async_include_methods
from ..validators import validate_jsonrpc_request as validate_request

logger = structlog.get_logger(__name__)


@async_include_methods(include_http_methods=('POST',))
@handle_middleware_exceptions
async def validate_jsonrpc_request(
        request: HTTPRequest) -> Optional[HTTPResponse]:
    try:
        _ = request.jsonrpc
    except InvalidRequest as e:
        return InvalidRequest(sanic_request=request,
                              exception=e).to_sanic_response()
    except ParseError as e:
        return ParseError(sanic_request=request,
                          exception=e).to_sanic_response()
    except Exception as e:
        return ParseError(sanic_request=request, exception=e).to_sanic_response()

    try:
        validate_request(jsonrpc_request=request.json)
    except (AssertionError, TypeError, KeyError) as e:
        # invalid jsonrpc
        return InvalidRequest(sanic_request=request, exception=e).to_sanic_response()
    except (InvalidUsage, ValueError) as e:
        return ParseError(sanic_request=request, exception=e).to_sanic_response()
    except Exception as e:
        # json failed to parse
        return ServerError(sanic_request=request, exception=e).to_sanic_response()
