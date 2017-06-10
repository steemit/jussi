# coding=utf-8
import logging


from sanic import response

from utils import replace_jsonrpc_id
from utils import strip_steemd_method_namespace
from utils import sort_request
from utils import jussi_attrs
from cache import cache_get

logger = logging.getLogger('sanic')




async def jsonrpc_id_to_str(request):
    """Assure all jsonrpc ids are strings (steemd needs this)

    Args:
        request:

    Returns:
        None
    """
    request_json = replace_jsonrpc_id(request.json)
    logger.debug('middlewares.request.jsonrpc_id_to_str %s --> %s',
                 request.json, request_json)
    request.parsed_json = request_json


async def sort_request_for_cache(request):
    request.parsed_json = sort_request(request.json)


async def add_jussi_attrs(request):
    request = await jussi_attrs(request)
    logger.debug('request.jussi: %s', request['jussi'])


async def fix_steemd_method_namespace(request):
    """Remove  'steemd.' from steemd jsonrpc methods

    Args:
        request:

    Returns:

    """
    request.parsed_json = strip_steemd_method_namespace(request.json)


async def caching_middleware(request):
    if not request['jussi_is_batch']:
        jussi_attrs = request['jussi']
        cached_response = await cache_get(request.app, jussi_attrs)
        if cached_response:
            return response.json(cached_response)
