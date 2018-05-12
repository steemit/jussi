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
from ..utils import async_include_methods
from ..validators import validate_jsonrpc_request as validate_request

import structlog
logger = structlog.get_logger(__name__)


@async_include_methods(include_http_methods=('POST',))
@handle_middleware_exceptions
async def validate_jsonrpc_request(
        request: HTTPRequest) -> Optional[HTTPResponse]:
    try:
        _ = request.json
    except Exception as e:
        return response.json(
            ParseError(sanic_request=request, exception=e).to_dict())
    try:
        validate_request(jsonrpc_request=request.json)
    except (AssertionError, TypeError) as e:
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
