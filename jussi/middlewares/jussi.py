# -*- coding: utf-8 -*-
import logging
import time
import uuid

from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..upstream.urn import x_jussi_urn

logger = logging.getLogger(__name__)


@handle_middleware_exceptions
async def add_jussi_request_id(request: HTTPRequest) -> None:
    request.headers['x-jussi-request-id'] = f's{uuid.uuid4()}'
    request['timing'] = time.perf_counter()


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    jussi_request_id = request.headers.get('x-jussi-request-id')
    # pylint: disable=bare-except
    if request.method == 'POST':
        try:
            request_urn = x_jussi_urn(request.json)
        except BaseException as e:
            logger.error('urn error: %s', e)
            request_urn = 'null'
    else:
        request_urn = request.path
    request_elapsed = time.perf_counter() - request['timing']
    logger.info(
        dict(
            request_id=jussi_request_id,
            request_urn=request_urn,
            request_elapsed=request_elapsed))
    response.headers['x-jussi-urn'] = request_urn
    response.headers['x-jussi-response-id'] = f'{jussi_request_id}->{uuid.uuid4()}'
    response.headers['x-jussi-response-time'] = request_elapsed
