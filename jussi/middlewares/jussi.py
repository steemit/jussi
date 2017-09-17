# -*- coding: utf-8 -*-
import logging
import uuid

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from ..errors import handle_middleware_exceptions

logger = logging.getLogger(__name__)


@handle_middleware_exceptions
async def add_jussi_request_id(request: HTTPRequest) -> None:
    jussi_request_id = request.headers.get('x-jussi-request-id')
    if not jussi_request_id:
        request.headers['x-jussi-request-id'] = f's{uuid.uuid4()}'


@handle_middleware_exceptions
async def add_jussi_response_id(request: HTTPRequest,
                                response: HTTPResponse) -> None:
    jussi_request_id = request.headers.get('x-jussi-request-id')
    response.headers['x-jussi-response-id'] = f'{jussi_request_id}->{uuid.uuid4()}'
