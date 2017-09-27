# -*- coding: utf-8 -*-
import logging
import uuid

from ..cache.utils import jsonrpc_cache_key
from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..upstream.url import url_from_urn
from ..upstream.urn import urn
from ..upstream.urn import urn_parts
from ..utils import async_exclude_methods, is_batch_jsonrpc

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
    response.headers[
        'x-jussi-response-id'] = f'{jussi_request_id}->{uuid.uuid4()}'


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET',))
async def add_jussi_jrpc_data(request: HTTPRequest) -> None:
    request_json = request.json
    if is_batch_jsonrpc(request_json):
        request['jussi'] = []
    else:
        request['jussi'] = {}

        request['jussi']['urn_parts'] = urn_parts(request_json)
        request['jussi']['urn'] = urn(request_json)

        request['jussi']['upstream_url'] = url_from_urn(
            request_json['juss']['urn'])
        request['jussi']['cache_key'] = jsonrpc_cache_key(request_json)
