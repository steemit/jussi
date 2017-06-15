# coding=utf-8
import asyncio
import hashlib
import logging


logger = logging.getLogger('sanic')


def jsonrpc_cache_key(single_jsonrpc_request):
    if isinstance(single_jsonrpc_request.get('params'), dict):
        # the params dict should already be sorted, so no need to sort again
        params = tuple(single_jsonrpc_request['params'].items())
    else:
        params = tuple(single_jsonrpc_request.get('params', []))

    return str(
        hashlib.sha1(('%s%s' % (params, single_jsonrpc_request['method'])
                      ).encode()).hexdigest())


async def cache_get(app, jussi_attrs):
    cache = app.config.cache
    logger.debug('%s.get(%s)', cache, jussi_attrs.key)
    response = await cache.get(jussi_attrs.key)
    if response:
        logger.debug(logger.debug('cache --> %s', response))
    return response


async def cache_set(app, value, jussi_attrs):
    # ttl of -1 means don't cache
    ttl = jussi_attrs.ttl

    if ttl < 0:
        logger.debug('skipping non-cacheable value %s', value)
        return
    elif ttl == 0:
        ttl = None
    cache = app.config.cache
    logger.debug('%s.set(%s, %s, ttl=%s)', cache, jussi_attrs.key, value, ttl)
    asyncio.ensure_future(cache.set(jussi_attrs.key, value, ttl=ttl))
