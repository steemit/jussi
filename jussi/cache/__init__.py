# -*- coding: utf-8 -*-

import time
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
POOL_IN_USE_MAX_AGE = 30              # JUSSI_REDIS_POOL_IN_USE_MAX_AGE (seconds)


class HealthCheckedConnectionPool(ConnectionPool):
    """ConnectionPool subclass that hardens the redis-py 4.x leak paths.

    Two independent leak modes are handled:

    1. ``release()`` is called on a dead/broken connection.
       redis-py 4.x's default ``release()`` happily appends such a
       connection back to ``_available_connections`` without decrementing
       ``_created_connections``. We override ``release()`` to disconnect
       and discard dead connections instead.

    2. ``release()`` is NEVER called on a connection.
       In jussi this is the dominant failure mode: the caching middleware
       wraps cache reads in ``async with timeout(cache_read_timeout):``.
       When that timeout fires asyncio cancels the task that holds the
       connection. Cancellation can propagate before redis-py's
       ``try/finally pool.release(conn)`` runs, leaving the connection
       stuck in ``_in_use_connections`` forever. The pool's bookkeeping
       eventually believes ``_created_connections >= max_connections``
       even though most of those "in use" connections are abandoned,
       producing ``ConnectionError("Too many connections")`` even though
       the server is idle.

    Mode 2 is handled by sweeping ``_in_use_connections`` on every
    ``get_connection()`` and evicting entries older than
    ``in_use_max_age`` seconds. Each connection is stamped with
    ``_jussi_in_use_since`` (monotonic time) when handed out and the
    stamp is cleared on legitimate release.
    """

    # Per-instance overridable (see setup_caches below).
    in_use_max_age = POOL_IN_USE_MAX_AGE

    async def get_connection(self, command_name, *keys, **options):
        await self._reap_stuck_in_use()
        connection = await super().get_connection(command_name, *keys, **options)
        connection._jussi_in_use_since = time.monotonic()
        return connection

    async def release(self, connection):
        """Release connection back to pool, discarding dead ones."""
        self._checkpid()
        async with self._lock:
            # Clear the in-use stamp regardless of outcome.
            connection.__dict__.pop('_jussi_in_use_since', None)
            try:
                self._in_use_connections.remove(connection)
            except KeyError:
                # Already evicted by the reaper — nothing more to do here;
                # _created_connections was decremented when the reaper ran.
                return

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

    async def _reap_stuck_in_use(self):
        """Evict in-use connections older than ``in_use_max_age`` seconds.

        Called opportunistically from ``get_connection()`` so it runs on
        the hot path without needing a background task. The scan is O(N)
        over ``_in_use_connections`` (bounded by ``max_connections``), so
        the overhead is negligible.
        """
        now = time.monotonic()
        stuck = []
        async with self._lock:
            for c in list(self._in_use_connections):
                since = getattr(c, '_jussi_in_use_since', None)
                if since is None:
                    # Connection predates this code path (e.g. handed out
                    # before an upgrade). Stamp it now so it has a chance.
                    c._jussi_in_use_since = now
                    continue
                if now - since > self.in_use_max_age:
                    stuck.append((c, now - since))
                    self._in_use_connections.discard(c)
                    self._created_connections = max(0, self._created_connections - 1)
                    c.__dict__.pop('_jussi_in_use_since', None)
        if not stuck:
            return
        # Disconnect outside the lock — disconnect() awaits and we don't
        # want to block release()/get_connection() of other tasks.
        for c, _age in stuck:
            try:
                await c.disconnect()
            except Exception:
                pass
        logger.warning('reaped stuck in-use redis connections',
                       count=len(stuck),
                       oldest_age_seconds=max(age for _, age in stuck),
                       max_age=self.in_use_max_age,
                       created_now=self._created_connections,
                       in_use_now=len(self._in_use_connections))


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
    in_use_max_age = getattr(args, 'redis_pool_in_use_max_age',
                             POOL_IN_USE_MAX_AGE)
    logger.info('redis pool config',
                max_connections=max_conns,
                socket_connect_timeout=sock_connect_to,
                socket_timeout=sock_to,
                health_check_interval=health_iv,
                in_use_max_age=in_use_max_age)
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
            pool.in_use_max_age = in_use_max_age
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
                replica_pool.in_use_max_age = in_use_max_age
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
