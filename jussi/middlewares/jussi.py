# -*- coding: utf-8 -*-
import logging
import random
import time

from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..upstream.urn import URNParts
from ..upstream.urn import x_jussi_urn_parts

logger = logging.getLogger(__name__)
request_logger = logging.getLogger('jussi_request')

REQUEST_ID_TO_INT_TRANSLATE_TABLE = mt = str.maketrans('', '', '-.')


@handle_middleware_exceptions
async def add_jussi_request_id(request: HTTPRequest) -> None:
    try:
        rid = request.headers['x-jussi-request-id']
        request['request_id_int'] = int(rid.translate(mt)[:19])
    except BaseException:
        logger.warning('bad/missing x-jussi-request-id-header: %s',
                       request.headers.get('x-jussi-request-id'))
        rid = random.getrandbits(64)
        request.headers['x-jussi-request-id'] = rid
        request['request_id_int'] = int(str(rid)[:19])

    request['logger'] = request_logger
    request['timing'] = time.perf_counter()


@handle_middleware_exceptions
async def finalize_jussi_response(request: HTTPRequest,
                                  response: HTTPResponse) -> None:
    jussi_request_id = request.headers.get('x-jussi-request-id')
    # pylint: disable=bare-except
    log_extra = dict(jussi_request_id=jussi_request_id,
                     upstream_id_prefix=request['request_id_int'])
    if request.method == 'POST':
        try:
            parts = x_jussi_urn_parts(request.json)
            if isinstance(parts, URNParts):
                response.headers['x-jussi-namespace'] = parts.namespace
                response.headers['x-jussi-api'] = parts.api
                response.headers['x-jussi-method'] = parts.method
                response.headers['x-jussi-params'] = parts.params
                log_extra.update(namespace=parts.namespace,
                                 api=parts.api,
                                 method=parts.method,
                                 params=parts.params)
        except BaseException as e:
            logger.error('urn error: %s', e)

    request_elapsed = time.perf_counter() - request['timing']
    log_extra.update(request_elapsed=request_elapsed)
    request['logger'].info(log_extra)
    response.headers['x-jussi-request-id'] = jussi_request_id
    response.headers['x-jussi-response-time'] = request_elapsed
