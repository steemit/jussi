# -*- coding: utf-8 -*-
import asyncio
import datetime
from urllib.parse import urlparse
from aredis import StrictRedis
from collections import namedtuple
from typing import Any
from enum import IntEnum


import structlog


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
    caches = []
    if args.redis_url:
        try:
            redis_cache = StrictRedis().from_url(args.redis_url)
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
            logger.error('failed to add redis cache to caches', exception=e)
        if args.redis_read_replica_urls:
            for url in urlparse(args.redis_read_replica_hosts):
                logger.info('Adding redis read replicas',
                            read_replica=url,
                            host=url.hostname,
                            port=url.port)
                cache = StrictRedis().from_url(args.redis_url)
                if cache:
                    if args.cache_test_before_add:
                        try:
                            _ = asyncio.gather(cache.get('key'))
                        except Exception as e:
                            logger.error('failed to add cache', exception=e)
                        else:
                            caches.append(CacheGroupItem(cache=cache,
                                                         read=True,
                                                         write=False,
                                                         speed_tier=SpeedTier.SLOW))
                    else:
                        caches.append(
                            CacheGroupItem(cache=cache,
                                           read=True,
                                           write=False,
                                           speed_tier=SpeedTier.SLOW))

    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
