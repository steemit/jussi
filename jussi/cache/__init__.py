# -*- coding: utf-8 -*-
import logging
from typing import Any

import aiocache
import aiocache.backends

from .backends import SimpleMaxTTLMemoryCache
from .serializers import CompressionSerializer
from .cache_group import CacheGroup
from ..typedefs import WebApp


logger = logging.getLogger(__name__)


# pylint: disable=unused-argument
def setup_caches(app: WebApp, loop) -> Any:
    logger.info('before_server_start -> cache.setup_caches')
    args = app.config.args
    caches = [SimpleMaxTTLMemoryCache()]
    if args.redis_host:
        try:
            cache = aiocache.RedisCache(endpoint=args.redis_host,
                                        port=args.redis_port,
                                        timeout=args.cache_read_timeout,
                                        serializer=CompressionSerializer())

            if cache:
                caches.append(cache)
        except Exception:
            logger.exception('failed to add redis cache to caches')

    if args.memcached_host:
        try:
            cache = aiocache.MemcachedCache(endpoint=args.memcached_host,
                                            port=args.memcached_port,
                                            timeout=args.cache_read_timeout,
                                            serializer=CompressionSerializer())

            if cache:
                caches.append(cache)
        except Exception:
            logger.exception('failed to add memcached cache to caches')
    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
