# -*- coding: utf-8 -*-
from typing import Optional
from reprlib import repr as _repr
from time import perf_counter as perf

import structlog

from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..errors import JsonRpcError

logger = structlog.get_logger('jussi')


async def initialize_jussi_request(request: HTTPRequest) -> Optional[HTTPResponse]:
   # parse jsonrpc
    try:
        request.jsonrpc
    except JsonRpcError as e:
        return e.to_sanic_response()
    except Exception as e:
        return JsonRpcError(http_request=request,
                            exception=e).to_sanic_response()


async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    # pylint: disable=bare-except
    try:
        response.headers['x-jussi-request-id'] = request.jussi_request_id
        response.headers['x-amzn-trace-id'] = request.amzn_trace_id
        response.headers['x-jussi-response-time'] = str(perf() - request.timings[0][0])
        if request.is_single_jrpc:
            response.headers['x-jussi-namespace'] = request.jsonrpc.urn.namespace
            response.headers['x-jussi-api'] = request.jsonrpc.urn.api
            response.headers['x-jussi-method'] = request.jsonrpc.urn.method
            response.headers['x-jussi-params'] = _repr(request.jsonrpc.urn.params)

    except BaseException as e:
        logger.warning('finalize_jussi error', e=e)
