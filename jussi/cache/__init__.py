# -*- coding: utf-8 -*-
import asyncio
import datetime


from collections import namedtuple
from typing import Any
from enum import IntEnum

import aiocache
import aiocache.backends
import structlog

from .backends.max_ttl import SimpleMaxTTLMemoryCache
from .serializers import CompressionSerializer
from .cache_group import CacheGroup
from ..typedefs import WebApp

logger = structlog.get_logger(__name__)


class SpeedTier(IntEnum):
    SLOW = 1
    FAST = 2
    FASTEST = 3


CacheGroupItem = namedtuple('CacheGroupItem', ('cache', 'read', 'write', 'speed_tier'))


# pylint: disable=unused-argument,too-many-branches,too-many-nested-blocks
def setup_caches(app: WebApp, loop) -> Any:
    logger.info('cache.setup_caches', when='before_server_start')
    args = app.config.args

    caches = [CacheGroupItem(cache=SimpleMaxTTLMemoryCache(),
                             read=True,
                             write=True,
                             speed_tier=SpeedTier.FASTEST)
              ]
    if args.redis_host:
        try:
            redis_cache = aiocache.RedisCache(endpoint=args.redis_host,
                                              port=args.redis_port,
                                              pool_min_size=args.redis_pool_minsize,
                                              pool_max_size=args.redis_pool_maxsize,
                                              serializer=CompressionSerializer())
            if redis_cache:
                if args.cache_test_before_add:
                    value = datetime.datetime.utcnow().isoformat()
                    try:
                        _ = asyncio.gather(redis_cache.set('key', value, ttl=60))
                        value2 = asyncio.gather(redis_cache.get('key'))
                        assert value == value2.result()
                    except Exception as e:
                        logger.exception('failed to add cache', exc_info=e)
                    else:
                        caches.append(CacheGroupItem(cache=redis_cache,
                                                     read=False,
                                                     write=True,
                                                     speed_tier=SpeedTier.SLOW))
                else:
                    caches.append(CacheGroupItem(cache=redis_cache,
                                                 read=False,
                                                 write=True,
                                                 speed_tier=SpeedTier.SLOW))
        except Exception as e:
            logger.exception('failed to add redis cache to caches', exc_info=e)
        if args.redis_read_replica_hosts:
            for host in args.redis_read_replica_hosts:
                if ':' in host:
                    host, port = host.split(':')
                else:
                    port = args.redis_port
                logger.info('Adding redis read replicas',
                            read_replica=args.redis_read_replica_hosts,
                            host=host,
                            port=port)
                cache = aiocache.RedisCache(endpoint=host,
                                            port=port,
                                            pool_min_size=args.redis_pool_minsize,
                                            pool_max_size=args.redis_pool_maxsize,
                                            serializer=CompressionSerializer())
                if cache:
                    if args.cache_test_before_add:
                        try:
                            _ = asyncio.gather(cache.get('key'))
                        except Exception as e:
                            logger.exception('failed to add cache', exc_info=e)
                        else:
                            caches.append(CacheGroupItem(cache=cache,
                                                         read=True,
                                                         write=False,
                                                         speed_tier=SpeedTier.FAST))
                    else:
                        caches.append(
                            CacheGroupItem(cache=cache,
                                           read=True,
                                           write=False,
                                           speed_tier=SpeedTier.FAST))

    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
