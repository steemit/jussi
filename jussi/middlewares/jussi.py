# -*- coding: utf-8 -*-
import logging
import random
import reprlib
from reprlib import repr
from time import perf_counter

import structlog


from ..errors import handle_middleware_exceptions
from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

logger = structlog.get_logger(__name__)
request_logger = structlog.getLogger('jussi_request')


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    # pylint: disable=bare-except
    try:
        response.headers['x-jussi-request-id'] = request.jussi_request_id
        response.headers['x-amzn-trace-id'] = request.amzn_trace_id
        now = perf_counter()
        response.headers['x-jussi-response-time'] = str(now - request._timings['created'])

        if request.method == 'POST' and isinstance(request.jsonrpc, JussiJSONRPCRequest):
            response.headers['x-jussi-namespace'] = request.jsonrpc.urn.namespace
            response.headers['x-jussi-api'] = request.jsonrpc.urn.api
            response.headers['x-jussi-method'] = request.jsonrpc.urn.method
            response.headers['x-jussi-params'] = repr(request.jsonrpc.urn.params)

    except BaseException as e:
        logger.warning('finalize_jussi error', exc_info=e)
