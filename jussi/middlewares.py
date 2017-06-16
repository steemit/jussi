# coding=utf-8
import logging

from sanic import response

from .cache import cache_get
from .utils import jussi_attrs
from .utils import replace_jsonrpc_id
from .utils import sort_request

logger = logging.getLogger('sanic')


async def add_jussi_attrs(request):
    #request.parsed_json = replace_jsonrpc_id(request.json)
    request.parsed_json = sort_request(request.json)
    request = await jussi_attrs(request)
    logger.debug('request.jussi: %s', request['jussi'])


async def caching_middleware(request):
    if request['jussi_is_batch']:
        logger.debug('skipping cache for jsonrpc batch request')
        return
    jussi_attrs = request['jussi']
    cached_response = await cache_get(request.app, jussi_attrs)
    if cached_response:
        return response.raw(
            cached_response,
            content_type='application/json',
            headers={'x-jussi-cache-hit': jussi_attrs.key})
