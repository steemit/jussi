# -*- coding: utf-8 -*-
import gzip
import logging
import zlib
from io import BytesIO
from typing import Optional

from sanic import response
from sanic.exceptions import InvalidUsage

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from .cache import cache_get
from .cache import cache_get_batch
from .cache import jsonrpc_cache_key
from .cache import merge_cached_response
from .errors import InvalidRequest
from .errors import ParseError
from .errors import ServerError
from .errors import handle_middleware_exceptions
from .utils import async_exclude_methods
from .utils import is_batch_jsonrpc
from .utils import is_valid_jsonrpc_request
from .utils import sort_request
from .utils import stats_key

logger = logging.getLogger('sanic')


def decode_gzip(data):
    gzipper = gzip.GzipFile(fileobj=BytesIO(data))
    return gzipper.read()


def decode_deflate(data):
    try:
        return zlib.decompress(data)
    except zlib.error:
        return zlib.decompress(data, -zlib.MAX_WBITS)


CONTENT_DECODERS = {
    'gzip': decode_gzip,
    'deflate': decode_deflate,
}


def setup_middlewares(app):
    logger = app.config.logger
    logger.info('before_server_start -> setup_middlewares')
    app.request_middleware.append(handle_gzip)
    app.request_middleware.append(validate_jsonrpc_request)
    app.request_middleware.append(request_stats)
    app.request_middleware.append(caching_middleware)
    app.response_middleware.append(finalize_request_stats)
    return app


@handle_middleware_exceptions
async def handle_gzip(request: HTTPRequest) -> Optional[HTTPResponse]:
    content_encoding = request.headers.get('content-encoding')
    decoder = CONTENT_DECODERS.get(content_encoding)
    try:
        if decoder:
            request.body = decoder(request.body)
    except (IOError, zlib.error) as e:
        logger.error(e)
        return response.json(
            ParseError(sanic_request=request, exception=e).to_dict())


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def validate_jsonrpc_request(
        request: HTTPRequest) -> Optional[HTTPResponse]:
    try:
        is_valid_jsonrpc_request(single_jsonrpc_request=request.json)
        request.parsed_json = sort_request(single_jsonrpc_request=request.json)
    except AssertionError as e:
        # invalid jsonrpc
        return response.json(
            InvalidRequest(sanic_request=request, exception=e).to_dict())
    except (InvalidUsage, ValueError) as e:
        return response.json(
            ParseError(sanic_request=request, exception=e).to_dict())
    except Exception as e:
        # json failed to parse
        return response.json(
            ServerError(sanic_request=request, exception=e).to_dict())


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def request_stats(request: HTTPRequest) -> Optional[HTTPResponse]:
    stats = request.app.config.stats
    if is_batch_jsonrpc(sanic_http_request=request):
        stats.incr('jsonrpc.batch_requests')
        for req in request.json:
            key = stats_key(req)
            stats.incr('jsonrpc.requests.%s' % key)
        return
    key = stats_key(request.json)
    stats.incr('jsonrpc.single_requests')
    stats.incr('jsonrpc.requests.%s' % key)
    request['timer'] = stats.timer('jsonrpc.requests.%s' % key)
    request['timer'].start()


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def caching_middleware(request: HTTPRequest) -> None:
    # return cached response from cache if all requests were in cache
    if is_batch_jsonrpc(sanic_http_request=request):
        logger.debug(
            'caching_middleware attemping to load batch request from cache')
        cached_response = await cache_get_batch(request.app.config.caches, request.json)
        if all(cached_response):
            logger.debug('caching_middleware loaded batch request from cache')
            return response.json(cached_response, headers={
                                 'x-jussi-cache-hit': 'batch'})
        else:
            request['cached_response'] = cached_response
        logger.debug(
            'caching_middleware unable to load batch request from cache')
        return

    key = jsonrpc_cache_key(request.json)
    logger.debug('caching_middleware cache_get %s', key)
    cached_response = await cache_get(request, request.json)

    if cached_response:
        logger.debug('caching_middleware hit for %s', key)
        cached_response = merge_cached_response(cached_response, request.json)
        return response.json(
            cached_response, headers={'x-jussi-cache-hit': key})

    logger.debug('caching_middleware no hit for %s', key)


# pylint: disable=unused-argument
@handle_middleware_exceptions
async def finalize_request_stats(request: HTTPRequest,
                                 response: HTTPResponse) -> None:
    if 'timer' in request:
        request['timer'].stop()
