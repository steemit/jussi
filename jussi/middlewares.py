# -*- coding: utf-8 -*-
import logging
import time

from sanic import response
from sanic.exceptions import InvalidUsage

from .cache import cache_get
from .errors import InvalidRequest
from .errors import ParseError
from .errors import ServerError
from .errors import handle_middleware_exceptions
from .timers import init_timers
from .timers import log_timers
from .utils import async_exclude_methods
from .utils import is_valid_jsonrpc_request
from .utils import jussi_attrs
from .utils import sort_request

logger = logging.getLogger('sanic')


@handle_middleware_exceptions
async def start_stats(request):
    request['timers'] = init_timers(start_time=time.time())
    request['statsd'] = request.app.config.statsd_client.pipeline()


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def validate_jsonrpc_request(request):
    try:
        assert is_valid_jsonrpc_request(request.json)
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
async def add_jussi_attrs(request):
    # request.json handles json parse errors, this handles empty json
    request.parsed_json = sort_request(request.json)
    request = await jussi_attrs(request)
    logger.debug('request.jussi: %s', request['jussi'])


@handle_middleware_exceptions
@async_exclude_methods(exclude_http_methods=('GET', ))
async def caching_middleware(request):
    if request['jussi_is_batch']:
        logger.debug('skipping cache for jsonrpc batch request')
        return
    jussi_attrs = request['jussi']
    with request['timers']['caching_middleware']:
        cached_response = await cache_get(request, jussi_attrs)

    if cached_response:
        return response.raw(
            cached_response,
            content_type='application/json',
            headers={'x-jussi-cache-hit': jussi_attrs.key})


# pylint: disable=unused-argument
async def finalize_timers(request, response):
    if request.get('timers'):
        end = time.time()
        logger.info('skipped finalizing timers, no timers to finalize')
        request['timers']['total_jussi_elapsed'].end()
        for timer in request['timers'].values():
            timer.end(end)
        log_timers(request.get('timers'), logger.debug)


async def log_stats(request, response):
    if request.get('timers'):
        logger.info('skipped logging timers, no timers to log')
        log_timers(request.get('timers'), logger.info)
        try:
            pipe = request['statsd']
            logger.debug(pipe._stats)  # pylint: disable=protected-access
            for name, timer in request['timers'].items():
                pipe.timing(name, timer.elapsed)
            pipe.send()
        except Exception as e:
            logger.warning('Failed to send stats to statsd: %s', e)
