# -*- coding: utf-8 -*-
import asyncio
import collections
import logging
from inspect import isawaitable

from websockets import connect as websockets_connect

from .utils import PY_35
from .utils import _PoolAcquireContextManager
from .utils import _PoolConnectionContextManager
from .utils import _PoolContextManager
from .utils import create_future
from .utils import ensure_future


async def connect(url=None, **kwargs):
    return await websockets_connect(uri=url, **kwargs)


logger = logging.getLogger('jussi')


def create_pool(url=None, *, minsize=1, maxsize=10,
                loop=None, timeout=5, pool_recycle=-1, **kwargs):
    coro = _create_pool(url=url, minsize=minsize, maxsize=maxsize,
                        loop=loop, timeout=timeout, pool_recycle=pool_recycle, **kwargs)
    return _PoolContextManager(coro)


async def _create_pool(url=None, *, minsize=1, maxsize=10,
                       loop=None, timeout=5, pool_recycle=-1, **kwargs):
    # pylint: disable=protected-access
    if loop is None:
        loop = asyncio.get_event_loop()

    pool = Pool(url=url, minsize=minsize, maxsize=maxsize,
                loop=loop, timeout=timeout, pool_recycle=pool_recycle, **kwargs)
    if minsize > 0:
        with (await pool._cond):
            await pool._fill_free_pool(False)
    return pool


class Pool(asyncio.AbstractServer):
    """Connection pool"""
    # pylint: disable=too-many-instance-attributes,too-many-arguments
    def __init__(self, url, minsize, maxsize, loop,
                 timeout, *, pool_recycle, **kwargs):
        if minsize < 0:
            raise ValueError("minsize should be zero or greater")
        if maxsize < minsize and maxsize != 0:
            raise ValueError("maxsize should be not less than minsize")
        self._url = url
        self._minsize = minsize
        self._loop = loop
        self._timeout = timeout
        self._recycle = pool_recycle

        self._on_connect = None  # on_connect
        self._conn_kwargs = kwargs
        self._acquiring = 0
        self._free = collections.deque(maxlen=maxsize or None)
        self._cond = asyncio.Condition(loop=loop)
        self._used = set()
        self._terminated = set()
        self._closing = False
        self._closed = False

    @property
    def minsize(self):
        return self._minsize

    @property
    def maxsize(self):
        return self._free.maxlen

    @property
    def size(self):
        return self.freesize + len(self._used) + self._acquiring

    @property
    def freesize(self):
        return len(self._free)

    @property
    def timeout(self):
        return self._timeout

    @asyncio.coroutine
    def clear(self):
        """Close all free connections in pool."""
        with (yield from self._cond):
            while self._free:
                conn = self._free.popleft()
                yield from conn.close()
            self._cond.notify()

    @property
    def closed(self):
        return self._closed

    def close(self):
        """Close pool.

        Mark all pool connections to be closed on getting back to pool.
        Closed pool doesn't allow to acquire new connections.
        """
        if self._closed:
            return
        self._closing = True

    def terminate(self):
        """Terminate pool.

        Close pool with instantly closing all acquired connections also.
        """

        self.close()

        for conn in list(self._used):
            if isawaitable(conn.close):
                self._loop.run_until_complete(conn.close())
            else:
                conn.close()
            self._terminated.add(conn)

        self._used.clear()

    @asyncio.coroutine
    def wait_closed(self):
        """Wait for closing all pool's connections."""

        if self._closed:
            return
        if not self._closing:
            raise RuntimeError(".wait_closed() should be called "
                               "after .close()")

        while self._free:
            conn = self._free.popleft()
            if isawaitable(conn.close):
                self._loop.run_until_complete(conn.close())
            else:
                conn.close()

        with (yield from self._cond):
            while self.size > self.freesize:
                yield from self._cond.wait()

        self._closed = True

    def acquire(self):
        """Acquire free connection from the pool."""
        coro = self._acquire()
        return _PoolAcquireContextManager(coro, self)

    @asyncio.coroutine
    def _acquire(self):
        if self._closing:
            raise RuntimeError("Cannot acquire connection after closing pool")
        with (yield from self._cond):
            while True:
                yield from self._fill_free_pool(True)
                if self._free:
                    conn = self._free.popleft()
                    assert conn.open, conn
                    assert conn not in self._used, (conn, self._used)
                    self._used.add(conn)
                    # pylint: disable=not-callable
                    if self._on_connect is not None:
                        yield from self._on_connect(conn)
                    return conn
                else:
                    yield from self._cond.wait()

    @asyncio.coroutine
    def _fill_free_pool(self, override_min):
        # pylint: disable=no-value-for-parameter
        # iterate over free connections and remove timeouted ones
        n, free = 0, len(self._free)
        while n < free:
            conn = self._free[-1]
            if not conn.open:
                self._free.pop()

            elif self._recycle > -1 \
                    and self._loop.time() - conn.last_usage > self._recycle:
                conn.close()

                self._free.pop()
            else:
                self._free.rotate()
            n += 1

        while self.size < self.minsize:
            logger.debug('opening ws connection')
            self._acquiring += 1
            try:
                conn = yield from connect(
                    self._url, loop=self._loop, timeout=self._timeout, **self._conn_kwargs)
                # raise exception if pool is closing
                self._free.append(conn)
                self._cond.notify()
            finally:
                self._acquiring -= 1
        if self._free:
            return

        if override_min and self.size < self.maxsize:
            self._acquiring += 1
            try:
                conn = yield from connect(
                    self._url, loop=self._loop, timeout=self._timeout, **self._conn_kwargs)
                # raise exception if pool is closing
                self._free.append(conn)
                self._cond.notify()
            finally:
                self._acquiring -= 1

    @asyncio.coroutine
    def _wakeup(self):
        with (yield from self._cond):
            self._cond.notify()

    def release(self, conn):
        """Release free connection back to the connection pool.
        """
        fut = create_future(self._loop)
        fut.set_result(None)
        if conn in self._terminated:
            assert not conn.open, conn
            self._terminated.remove(conn)
            return fut
        assert conn in self._used, (conn, self._used)
        self._used.remove(conn)
        if conn.open:
            logger.debug('releasing')
            if self._closing:
                conn.close()
            else:
                self._free.append(conn)
            fut = ensure_future(self._wakeup(), loop=self._loop)
        return fut

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        # This must exist because __enter__ exists, even though that
        # always raises; that's how the with-statement works.
        pass  # pragma: nocover

    def __iter__(self):
        # This is not a coroutine.  It is meant to enable the idiom:
        #
        #     with (yield from pool) as conn:
        #         <block>
        #
        # as an alternative to:
        #
        #     conn = yield from pool.acquire()
        #     try:
        #         <block>
        #     finally:
        #         conn.release()
        conn = yield from self.acquire()
        return _PoolConnectionContextManager(self, conn)

    if PY_35:  # pragma: no branch
        @asyncio.coroutine
        def __aenter__(self):
            return self

        @asyncio.coroutine
        def __aexit__(self, exc_type, exc_val, exc_tb):
            self.close()
            yield from self.wait_closed()
