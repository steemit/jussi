# -*- coding: utf-8 -*-

from urllib.parse import urlparse
from collections import namedtuple
from typing import Any
from enum import IntEnum

import structlog

from aredis import StrictRedis


from .cache_group import CacheGroup
from ..typedefs import WebApp
from .backends.redis import Cache

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
            redis_client = StrictRedis().from_url(args.redis_url)
            redis_cache = Cache(redis_client)
            if redis_cache:
                caches.append(CacheGroupItem(cache=redis_cache,
                                             read=False,
                                             write=True,
                                             speed_tier=SpeedTier.SLOW))
        except Exception as e:
            logger.error('failed to add redis cache to caches', exception=e)
        if args.redis_read_replica_urls:
            for url_string in args.redis_read_replica_urls:
                url = urlparse(url_string)
                logger.info('Adding redis read replicas',
                            read_replica=url,
                            host=url.hostname,
                            port=url.port)
                redis_client = StrictRedis().from_url(url_string)
                redis_cache = Cache(redis_client)
                if redis_cache:
                    caches.append(
                        CacheGroupItem(cache=redis_cache,
                                       read=True,
                                       write=False,
                                       speed_tier=SpeedTier.SLOW))

    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
