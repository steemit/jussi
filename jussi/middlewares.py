# -*- coding: utf-8 -*-
import logging
from typing import Optional

from sanic import response
from sanic.exceptions import InvalidUsage

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from .cache import cache_get
from .errors import InvalidRequest
from .errors import ParseError
from .errors import ServerError
from .errors import handle_middleware_exceptions
from .utils import async_exclude_methods
from .utils import is_valid_jsonrpc_request
from .utils import jussi_attrs
from .utils import sort_request

logger = logging.getLogger('sanic')


def setup_middlewares(app):
    logger = app.config.logger
    logger.info('before_server_start -> setup_middlewares')
    app.request_middleware.append(validate_jsonrpc_request)
    app.request_middleware.append(add_jussi_attrs)
    app.request_middleware.append(caching_middleware)

    return app


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def validate_jsonrpc_request(
    request: HTTPRequest) -> Optional[HTTPResponse]:
    try:
        is_valid_jsonrpc_request(request.json)
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
async def add_jussi_attrs(request: HTTPRequest) -> None:
    # request.json handles json parse errors, this handles empty json
    request.parsed_json = sort_request(request.json)
    request = await jussi_attrs(request)
    logger.debug('request.jussi: %s', request['jussi'])


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def caching_middleware(request: HTTPRequest) -> None:
    if request['jussi_is_batch']:
        logger.debug('skipping cache for jsonrpc batch request')
        return
    jussi_attrs = request['jussi']

    cached_response = await cache_get(request, jussi_attrs)

    if cached_response:
        return response.raw(
            cached_response,
            content_type='application/json',
            headers={'x-jussi-cache-hit': jussi_attrs.key})
