# -*- coding: utf-8 -*-
from time import perf_counter as perf
from reprlib import repr
import structlog

from ..errors import handle_middleware_exceptions
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
        now = perf()
        response.headers['x-jussi-response-time'] = str(now - request.timings[0][0])
        request.app.config.statsd_client.from_timings(request.timings)
        if request.is_single_jrpc:
            response.headers['x-jussi-namespace'] = request.jsonrpc.urn.namespace
            response.headers['x-jussi-api'] = request.jsonrpc.urn.api
            response.headers['x-jussi-method'] = request.jsonrpc.urn.method
            response.headers['x-jussi-params'] = repr(request.jsonrpc.urn.params)
            request.app.config.statsd_client.from_timings(request.jsonrpc.timings)
        elif request.is_batch_jrpc:
            for r in request.jsonrpc:
                request.app.config.statsd_client.from_timings(r.timings)
        request.app.config.statsd_client._sendbatch()
    except BaseException as e:
        logger.warning('finalize_jussi error', e=e)
