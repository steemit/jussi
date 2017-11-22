# -*- coding: utf-8 -*-
import asyncio
import collections
import logging

from websockets import connect as websockets_connect

from .utils import PY_35
from .utils import _PoolAcquireContextManager
from .utils import _PoolConnectionContextManager
from .utils import create_future
from .utils import ensure_future

logger = logging.getLogger(__name__)

'''
websocket connection memory usage = 4 bytes * MAX_WEBSOCKET_RECV_SIZE * MAX_WEBSOCKET_RECV_QUEUE [ * connections in pool]

The ``timeout`` parameter defines the maximum wait time in seconds for
completing the closing handshake and, only on the client side, for
terminating the TCP connection. :meth:`close()` will complete in at most
this time on the server side and twice this time on the client side.

The ``MAX_WEBSOCKET_RECV_SIZE`` parameter enforces the maximum size for incoming messages
in bytes. The default value is 1MB. ``None`` disables the limit. If a
message larger than the maximum size is received, :meth:`recv()` will
raise :exc:`~websockets.exceptions.ConnectionClosed` and the connection
will be closed with status code 1009.

The ``MAX_WEBSOCKET_RECV_QUEUE`` parameter sets the maximum length of the queue that holds
incoming messages. The default value is 32. 0 disables the limit. Messages
are added to an in-memory queue when they're received; then :meth:`recv()`
pops from that queue. In order to prevent excessive memory consumption when
messages are received faster than they can be processed, the queue must be
bounded. If the queue fills up, the protocol stops processing incoming data
until :meth:`recv()` is called. In this situation, various receive buffers
(at least in ``asyncio`` and in the OS) will fill up, then the TCP receive
window will shrink, slowing down transmission to avoid packet loss.

Since Python can use up to 4 bytes of memory to represent a single
character, each websocket connection may use up to ``4 * max_size *
max_queue`` bytes of memory to store incoming messages. By default,
this is 128MB. You may want to lower the limits, depending on your
application's requirements.

The ``MAX_WEBSOCKET_READ_LIMIT`` argument sets the high-water limit of the buffer for
incoming bytes. The low-water limit is half the high-water limit. The
default value is 64kB, half of asyncio's default (based on the current
implementation of :class:`~asyncio.StreamReader`).

The ``write_limit`` argument sets the high-water limit of the buffer for
outgoing bytes. The low-water limit is a quarter of the high-water limit.
The default value is 64kB, equal to asyncio's default (based on the
current implementation of ``_FlowControlMixin``).

'''
STEEMIT_MAX_BLOCK_SIZE = 65536  # get_dynamic_global_properties['maximum_block_size']
MAX_WEBSOCKET_RECV_SIZE = None  # no limit
MAX_WEBSOCKET_READ_LIMIT = STEEMIT_MAX_BLOCK_SIZE + 1000


async def connect(url=None, **kwargs):
    return await websockets_connect(uri=url,
                                    max_size=MAX_WEBSOCKET_RECV_SIZE,
                                    read_limit=MAX_WEBSOCKET_READ_LIMIT,
                                    **kwargs)


async def create_pool(url=None, *,
                      minsize=1,  # min connections in pool
                      maxsize=10,  # max connections in pool
                      loop=None,
                      timeout=1,  # timeout for closing handshake
                      pool_recycle=-1,  # recycle connection after x messages
                      **kwargs):
    # pylint: disable=protected-access
    if loop is None:
        loop = asyncio.get_event_loop()

    pool = Pool(url=url, minsize=minsize, maxsize=maxsize, loop=loop,
                timeout=timeout, pool_recycle=pool_recycle,
                **kwargs)
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
        self._connect_message_counter = collections.Counter()
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

    # pylint: disable=no-self-use
    def get_connection_info(self, conn):
        # pylint: disable=protected-access
        try:
            return {
                'conn_id': id(conn),
                'state': conn.state,
                'conn': conn,
                'conn.messages': str(conn.messages),
                'conn.messages.qsize': conn.messages.qsize(),
                'conn.messages.maxsize': conn.messages.maxsize,
                'conn.messages._unfinished_tasks': conn.messages._unfinished_tasks,
                'conn._stream_reader._buffer': conn._stream_reader._buffer
            }
        except Exception as e:
            logger.info(f'get_connection_info error: {e}')
    # pylint: enable=no-self-use

    def get_pool_info(self):
        try:
            return {
                'url': self._url,
                'minsize': self.minsize,
                'maxsize': self.maxsize,
                'recycling': self._recycle,
                'timeout': self.timeout,
                'size': self.size,
                'freesize': self.freesize,
                'acquiring': self._acquiring,
                'free_conns': [self.get_connection_info(conn) for conn in self._free],
                'used_conns': [self.get_connection_info(conn) for conn in self._used],
                'terminated_conns': [self.get_connection_info(conn) for conn in self._terminated],
                'connection_message_counts': self._connect_message_counter
            }
        except Exception as e:
            logger.info(f'get_pool_info error: {e}')

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
            asyncio.run_coroutine_threadsafe(self.terminate_connection(conn), self._loop)
        self._used.clear()

    async def terminate_connection(self, conn):
        try:
            logger.debug(f'terminating connection:{id(conn)}')
            await asyncio.shield(conn.close_connection(force=True))
            conn.worker_task.cancel()
            conn.close()
            self._terminated.add(conn)
            self.release(conn)
        except Exception as e:
            logger.exception(e)
            self._terminated.remove(conn)

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
            logger.debug(f'closing free connection {conn}')
            yield from conn.close_connection(after_handshake=False)
            conn.transfer_data_task.cancel()

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
                    logger.debug(
                        f'pool connections free:{self.freesize} used: {len(self._used)} acquiring:{self._acquiring}')
                    logger.debug(f'conn_info:{self.get_connection_info(conn)}')
                    if self._recycle > -1:
                        logger.debug(
                            f'pool.conn.{id(conn)} handled messages:{self._connect_message_counter[id(conn)]}')
                    assert conn.open, conn
                    assert conn not in self._used, (conn, self._used)
                    self._used.add(conn)
                    # pylint: disable=not-callable
                    if self._on_connect is not None:
                        yield from self._on_connect(conn)
                    if self._recycle > -1:
                        self._connect_message_counter[id(conn)] += 1
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
                    and self._connect_message_counter[id(conn)] > self._recycle:
                yield from self.terminate_connection(conn)
                logger.debug(f'recycled connection id:{id(conn)}')
                self._connect_message_counter.clear()
                self._free.pop()
            else:
                self._free.rotate()
            n += 1

        while self.size < self.minsize:
            logger.debug('opening ws connection')
            self._acquiring += 1
            try:
                conn = yield from connect(
                    self._url, loop=self._loop, timeout=self._timeout,
                    **self._conn_kwargs)
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
                    self._url, loop=self._loop, timeout=self._timeout,
                    **self._conn_kwargs)
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
        logger.debug(f'releasing conn.info:{self.get_connection_info(conn)}')
        try:
            logger.info(f'conn.messages.get_nowait(): {conn.messages.get_nowait()}')
        except asyncio.queues.QueueEmpty:
            pass

        fut = create_future(self._loop)
        fut.set_result(None)
        if conn in self._terminated:
            assert not conn.open, conn
            self._terminated.remove(conn)
            return fut
        assert conn in self._used, (conn, self._used)
        assert conn.messages.empty() is True
        self._used.remove(conn)
        if conn.open:
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
