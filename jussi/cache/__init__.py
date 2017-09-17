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
        caches.append(aiocache.RedisCache(endpoint=args.redis_host,
                                          port=args.redis_port,
                                          timeout=10,
                                          serializer=CompressionSerializer()
                                          )
                      )

    cache_group = CacheGroup(caches=caches)
    return cache_group
