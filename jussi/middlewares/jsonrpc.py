# -*- coding: utf-8 -*-
from time import perf_counter

import structlog
from sanic.exceptions import InvalidUsage
from typing import Optional

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from ..errors import InvalidRequest
from ..errors import ParseError
from ..errors import handle_middleware_exceptions
from ..validators import validate_jsonrpc_request as validate_request

logger = structlog.get_logger(__name__)


@handle_middleware_exceptions
async def validate_jsonrpc_request(
        request: HTTPRequest) -> Optional[HTTPResponse]:
    if request.method != 'POST':
        return
    request.timings['validate_jsonrpc_request.enter'] = perf_counter()
    try:
        validate_request(request.json)
        _ = request.jsonrpc
    except (AssertionError, TypeError, KeyError) as e:
        # invalid jsonrpc
        return InvalidRequest(http_request=request,
                              exception=e).to_sanic_response()
    except (InvalidUsage, ValueError) as e:
        return ParseError(http_request=request,
                          exception=e).to_sanic_response()
    except ParseError as e:
        return ParseError(http_request=request,
                          exception=e).to_sanic_response()
    except Exception as e:
        return ParseError(http_request=request,
                          exception=e).to_sanic_response()
    request.timings['validate_jsonrpc_request.exit'] = perf_counter()
