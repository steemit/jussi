# -*- coding: utf-8 -*-
import asyncio
import datetime

import logging

from collections import namedtuple
from typing import Any
from enum import IntEnum

import aiocache
import aiocache.backends
import structlog

from .backends import SimpleMaxTTLMemoryCache
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
    logger.info('before_server_start -> cache.setup_caches')
    args = app.config.args

    caches = [CacheGroupItem(SimpleMaxTTLMemoryCache(), True, True, SpeedTier.FASTEST)]
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
                        logger.exception('failed to add cache: %s', e)
                    else:
                        caches.append(CacheGroupItem(redis_cache, True, True,
                                                     SpeedTier.SLOW))
                else:
                    caches.append(CacheGroupItem(redis_cache, True, True, SpeedTier.SLOW))
        except Exception:
            logger.exception('failed to add redis cache to caches')
        if args.redis_read_replica_hosts:
            logger.info('Adding redis read replicas: %s', args.redis_read_replica_hosts)
            for host in args.redis_read_replica_hosts:
                cache = aiocache.RedisCache(endpoint=host,
                                            port=6379,
                                            pool_min_size=args.redis_pool_minsize,
                                            pool_max_size=args.redis_pool_maxsize,
                                            serializer=CompressionSerializer())
                if cache:
                    if args.cache_test_before_add:
                        try:
                            _ = asyncio.gather(cache.get('key'))
                        except Exception as e:
                            logger.exception('failed to add cache: %s', e)
                        else:
                            caches.append(CacheGroupItem(cache, True, False, SpeedTier.FAST))
                    else:
                        caches.append(
                            CacheGroupItem(cache, True, False, SpeedTier.FAST))

    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
