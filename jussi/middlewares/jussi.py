# -*- coding: utf-8 -*-
import logging
import random
import reprlib
import time

from ..errors import handle_middleware_exceptions
from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

import structlog
logger = structlog.get_logger(__name__)
request_logger = logging.getLogger('jussi_request')


@handle_middleware_exceptions
async def convert_to_jussi_request(request: HTTPRequest) -> None:
    # pylint: disable=no-member
    request['logger'] = request_logger
    request['timing'] = time.perf_counter()
    # the x-jussi-request-id header is not guaranteed to be there, eg, no nginx
    x_jussi_request_id = request.headers.get('x-jussi-request-id',
                                             '%(rid)018d' % {'rid': random.getrandbits(50)})

    # request['jussi_request_id'] is guaranteed to be there
    request['jussi_request_id'] = x_jussi_request_id

    if request.method == 'POST':

        jsonrpc_request = request.json
        if isinstance(jsonrpc_request, dict):
            request.parsed_json = JussiJSONRPCRequest.from_request(request, 0,
                                                                   jsonrpc_request
                                                                   )
        elif isinstance(jsonrpc_request, list):
            reqs = []
            for batch_index, single_jsonrpc_request in enumerate(jsonrpc_request):
                reqs.append(JussiJSONRPCRequest.from_request(request, batch_index,
                                                             single_jsonrpc_request
                                                             ))
            request.parsed_json = reqs


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    # pylint: disable=bare-except
    try:
        response.headers['x-jussi-request-id'] = request.get('jussi_request_id')
        response.headers['x-amzn-trace-id'] = request.headers.get('x-amzn-trace-id')
        now = time.perf_counter()
        response.headers['x-jussi-response-time'] = str(now - request.get('timing', now))

        if request.method == 'POST' and isinstance(request.json, JussiJSONRPCRequest):
            response.headers['x-jussi-namespace'] = request.json.urn.namespace
            response.headers['x-jussi-api'] = request.json.urn.api
            response.headers['x-jussi-method'] = request.json.urn.method
            response.headers['x-jussi-params'] = reprlib.repr(request.json.urn.params)

    except BaseException as e:
        logger.warning(e)
