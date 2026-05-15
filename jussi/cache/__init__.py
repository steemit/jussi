# -*- coding: utf-8 -*-

from urllib.parse import urlparse
from collections import namedtuple
from typing import Any
from enum import IntEnum

import structlog

from redis.asyncio import Redis
from redis.asyncio import ConnectionPool


from .cache_group import CacheGroup
from ..typedefs import WebApp
from .backends.redis import Cache

logger = structlog.get_logger(__name__)


class SpeedTier(IntEnum):
    SLOW = 1
    FAST = 2
    FASTEST = 3


CacheGroupItem = namedtuple('CacheGroupItem', ('cache', 'read', 'write', 'speed_tier'))

# Default pool config (env-overridable; see jussi/serve.py argparse)
# Historical defaults retained as fallback to keep behavior identical when
# --redis_pool_* args are not provided.
POOL_MAX_CONNECTIONS = 20             # JUSSI_REDIS_POOL_MAX_CONNECTIONS
POOL_SOCKET_CONNECT_TIMEOUT = 3       # JUSSI_REDIS_POOL_SOCKET_CONNECT_TIMEOUT (seconds)
POOL_SOCKET_TIMEOUT = 5               # JUSSI_REDIS_POOL_SOCKET_TIMEOUT (seconds)
POOL_RETRY_ON_TIMEOUT = True
POOL_HEALTH_CHECK_INTERVAL = 30       # JUSSI_REDIS_POOL_HEALTH_CHECK_INTERVAL (seconds)


class HealthCheckedConnectionPool(ConnectionPool):
    """ConnectionPool subclass that properly discards dead connections.

    redis-py 4.x has a bug where release() does not decrement
    _created_connections when a connection is returned to the pool,
    even if the connection is dead/broken. This causes _created_connections
    to grow until max_connections is reached, after which no new connections
    can be created — the same bug as aredis.

    This subclass overrides release() to check connection health and
    properly decrement the counter for dead connections.
    """

    async def release(self, connection):
        """Release connection back to pool, discarding dead ones."""
        self._checkpid()
        async with self._lock:
            try:
                self._in_use_connections.remove(connection)
            except KeyError:
                pass

            # Check if connection is actually alive before returning it
            if not self.owns_connection(connection) or not connection.is_connected:
                # Discard dead connection and allow a new one to be created
                self._created_connections -= 1
                try:
                    await connection.disconnect()
                except Exception:
                    pass
                return

            self._available_connections.append(connection)


# pylint: disable=unused-argument,too-many-branches,too-many-nested-blocks
def setup_caches(app: WebApp, loop) -> Any:
    logger.info('cache.setup_caches', when='before_server_start')
    args = app.config.args
    # Env-overridable pool config; fall back to module-level defaults when the
    # corresponding argparse attribute is missing (e.g. unit tests that build
    # an args object directly).
    max_conns = getattr(args, 'redis_pool_max_connections', POOL_MAX_CONNECTIONS)
    sock_connect_to = getattr(args, 'redis_pool_socket_connect_timeout',
                              POOL_SOCKET_CONNECT_TIMEOUT)
    sock_to = getattr(args, 'redis_pool_socket_timeout', POOL_SOCKET_TIMEOUT)
    health_iv = getattr(args, 'redis_pool_health_check_interval',
                        POOL_HEALTH_CHECK_INTERVAL)
    logger.info('redis pool config',
                max_connections=max_conns,
                socket_connect_timeout=sock_connect_to,
                socket_timeout=sock_to,
                health_check_interval=health_iv)
    caches = []
    if args.redis_url:
        try:
            pool = HealthCheckedConnectionPool.from_url(
                args.redis_url,
                max_connections=max_conns,
                socket_connect_timeout=sock_connect_to,
                socket_timeout=sock_to,
                retry_on_timeout=POOL_RETRY_ON_TIMEOUT,
                health_check_interval=health_iv,
            )
            redis_client = Redis(connection_pool=pool)
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
                replica_pool = HealthCheckedConnectionPool.from_url(
                    url_string,
                    max_connections=max_conns,
                    socket_connect_timeout=sock_connect_to,
                    socket_timeout=sock_to,
                    retry_on_timeout=POOL_RETRY_ON_TIMEOUT,
                    health_check_interval=health_iv,
                )
                redis_client = Redis(connection_pool=replica_pool)
                redis_cache = Cache(redis_client)
                if redis_cache:
                    caches.append(
                        CacheGroupItem(cache=redis_cache,
                                       read=True,
                                       write=False,
                                       speed_tier=SpeedTier.SLOW))

    configured_cache_group = CacheGroup(caches=caches)
    return configured_cache_group
