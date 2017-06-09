# coding=utf-8
import asyncio
import logging

logger = logging.getLogger(__name__)


def batch_jsonrpc_cache_key(batch_jussi_attrs):
    return tuple(r['jussi']['key'] for r in batch_jussi_attrs)


def jsonrpc_cache_key(single_jsonrpc_request):
    if isinstance(single_jsonrpc_request.get('params'), dict):
        params = tuple(single_jsonrpc_request['params'].items())
    else:
        params = tuple(single_jsonrpc_request.get('params',[]))

    return (params, single_jsonrpc_request['method'])


async def cache_get(app, jussi_attrs):
    cache = app.config.cache
    response = await cache.get(jussi_attrs.key)
    if response:
        logger.debug(logger.debug('cache(%s) --> %s', jussi_attrs.key, response))
    return response


async def cache_set(app, response, jussi_attrs):
    if not jussi_attrs.cacheable:
        return
    cache = app.config.cache
    asyncio.ensure_future(cache.set(jussi_attrs.key, response, ttl=jussi_attrs.ttl))