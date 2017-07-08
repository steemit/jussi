# coding=utf-8
import time
import logging

from sanic import response
from sanic.exceptions import InvalidUsage

from .cache import cache_get
from .utils import async_exclude_methods
from .utils import jussi_attrs
from .utils import replace_jsonrpc_id
from .utils import sort_request
from .timers import init_timers
from .timers import log_timers

logger = logging.getLogger('sanic')


async def start_stats(request):
    request['timers'] = init_timers(start_time=time.time())
    request['statsd'] = request.app.config.statsd_client.pipeline()


@async_exclude_methods(exclude_http_methods=('GET', ))
async def add_jussi_attrs(request):
    # request.json handles json parse errors, this handles empty json
    if not request.json:
        raise InvalidUsage('Bad jsonrpc request')
    request.parsed_json = sort_request(request.json)
    request = await jussi_attrs(request)
    logger.debug('request.jussi: %s', request['jussi'])


@async_exclude_methods(exclude_http_methods=('GET', ))
async def caching_middleware(request):
    if request['jussi_is_batch']:
        logger.debug('skipping cache for jsonrpc batch request')
        return
    jussi_attrs = request['jussi']
    with request['timers']['caching_middleware']:
        cached_response = await cache_get(request.app, jussi_attrs)

    if cached_response:
        return response.raw(
            cached_response,
            content_type='application/json',
            headers={'x-jussi-cache-hit': jussi_attrs.key})


async def finalize_timers(request, response):
    end = time.time()
    if not request.get('timers'):
        logger.info('skipped finalizing timers, no timers to finalize')
        return
    request['timers']['total_jussi_elapsed']
    for name, timer in request['timers'].items():
        timer.end(end)
    log_timers(request.get('timers'), logger.debug)


async def log_stats(request, response):
    if not request.get('timers'):
        logger.info('skipped logging timers, no timers to log')
        return
    log_timers(request.get('timers'), logger.info)

    try:
        pipe = request['statsd']
        logger.info(pipe._stats)
        for name, timer in request['timers'].items():
            pipe.timing(name, timer.elapsed)
        pipe.send()
    except Exception as e:
        logger.warning('Failed to send stats to statsd: %s', e)
