# -*- coding: utf-8 -*-
from time import perf_counter as perf
from reprlib import repr as _repr

import structlog

from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

logger = structlog.get_logger('jussi')


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    # pylint: disable=bare-except
    try:
        response.headers['x-jussi-request-id'] = request.jussi_request_id
        response.headers['x-amzn-trace-id'] = request.amzn_trace_id
        now = perf()
        response.headers['x-jussi-response-time'] = str(now - request.timings[0][0])
        if request.is_single_jrpc:
            response.headers['x-jussi-namespace'] = request.jsonrpc.urn.namespace
            response.headers['x-jussi-api'] = request.jsonrpc.urn.api
            response.headers['x-jussi-method'] = request.jsonrpc.urn.method
            response.headers['x-jussi-params'] = _repr(request.jsonrpc.urn.params)
    except BaseException as e:
        logger.warning('finalize_jussi error', e=e)
