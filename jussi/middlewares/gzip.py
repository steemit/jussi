# -*- coding: utf-8 -*-
import gzip
import logging
import zlib
from io import BytesIO

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from ..errors import handle_middleware_exceptions

logger = logging.getLogger(__name__)

COMPRESS_MIMETYPES = frozenset([
    'text/html',
    'text/css',
    'text/xml',
    'application/json',
    'application/javascript'])

COMPRESS_LEVEL = 6

COMPRESS_MIN_SIZE = 500


def decompress_gzip(data):
    gzipper = gzip.GzipFile(fileobj=BytesIO(data))
    return gzipper.read()


def decompress_deflate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return zlib.decompress(data, -zlib.MAX_WBITS)


def compress_gzip(response, compresslevel=None):
    return gzip.compress(
        response.body,
        compresslevel=compresslevel)


CONTENT_DECODERS = {
    'gzip': decompress_gzip,
    'deflate': decompress_deflate,
}


@handle_middleware_exceptions
async def decompress_request(request: HTTPRequest) -> None:
    content_encoding = request.headers.get('content-encoding')
    decoder = CONTENT_DECODERS.get(content_encoding)
    if decoder:
        request.body = decoder(request.body)


@handle_middleware_exceptions
async def compress_response(request: HTTPRequest,
                            response: HTTPResponse) -> HTTPResponse:
    accept_encoding = request.headers.get('Accept-Encoding', '')
    content_length = len(response.body)
    content_type = response.content_type

    if ';' in response.content_type:
        content_type = content_type.split(';')[0]

    # pylint: disable=too-many-boolean-expressions
    if (content_type not in COMPRESS_MIMETYPES or
        'gzip' not in accept_encoding.lower() or
            not 200 <= response.status < 300 or
            (content_length is not None and
             content_length < COMPRESS_MIN_SIZE) or
            'Content-Encoding' in response.headers):
        return response

    gzip_content = compress_gzip(response, compresslevel=COMPRESS_LEVEL)
    response.body = gzip_content

    response.headers['Content-Encoding'] = 'gzip'
    response.headers['Content-Length'] = len(response.body)

    vary = response.headers.get('Vary')
    if vary:
        if 'accept-encoding' not in vary.lower():
            response.headers['Vary'] = '{}, Accept-Encoding'.format(vary)
    else:
        response.headers['Vary'] = 'Accept-Encoding'

    return response
