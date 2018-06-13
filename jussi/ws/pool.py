# -*- coding: utf-8 -*-
import asyncio
from typing import NoReturn
from typing import Coroutine
from typing import Any

import collections

import structlog
from websockets import connect as websockets_connect
from websockets import WebSocketClientProtocol as WSConn


logger = structlog.get_logger(__name__)

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


async def connect(url=None, **kwargs) ->Coroutine[Any, None, WSConn]:
    return await websockets_connect(uri=url,
                                    max_size=MAX_WEBSOCKET_RECV_SIZE,
                                    read_limit=MAX_WEBSOCKET_READ_LIMIT,
                                    **kwargs)


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
    def minsize(self)-> int:
        return self._minsize

    @property
    def maxsize(self)-> int:
        return self._free.maxlen

    @property
    def size(self) -> int:
        return self.freesize + len(self._used) + self._acquiring

    @property
    def freesize(self) -> int:
        return len(self._free)

    @property
    def timeout(self) -> int:
        return self._timeout

    async def clear(self):
        """Close all free connections in pool."""
        async with self._cond:
            while self._free:
                conn = self._free.popleft()
                await conn.close()
            self._cond.notify()

    @property
    def closed(self) -> bool:
        return self._closed

    def close(self) -> NoReturn:
        """Close pool.

        Mark all pool connections to be closed on getting back to pool.
        Closed pool doesn't allow to acquire new connections.
        """
        if self._closed:
            return
        self._closing = True

    def terminate(self) -> NoReturn:
        """Terminate pool.

        Close pool with instantly closing all acquired connections also.
        """
        self.close()
        for conn in list(self._used):
            asyncio.run_coroutine_threadsafe(self.terminate_connection(conn), self._loop)
        self._used.clear()

    async def terminate_connection(self, conn: WSConn):
        try:
            if conn.open:
                await conn.close()
            self._terminated.add(conn)
            self.release(conn)
        except Exception as e:
            logger.error('conn termination error', e=e, conn=conn)
            if conn in self._terminated:
                self._terminated.remove(conn)

    async def wait_closed(self):
        """Wait for closing all pool's connections."""
        if self._closed:
            return
        if not self._closing:
            raise RuntimeError(".wait_closed() should be called "
                               "after .close()")
        while self._free:
            conn = self._free.popleft()
            logger.debug(f'closing free connection', conn=conn)
            await conn.close_connection(after_handshake=False)
            conn.transfer_data_task.cancel()

        async with self._cond:
            while self.size > self.freesize:
                await self._cond.wait()
        self._closed = True

    async def acquire(self):
        if self._closing:
            raise RuntimeError("Cannot acquire connection after closing pool")
        async with self._cond:
            while True:
                await self._fill_free_pool()
                if self._free:
                    conn = self._free.popleft()
                    assert conn.open and conn not in self._used
                    self._used.add(conn)
                    # pylint: disable=not-callable
                    if self._on_connect is not None:
                        await self._on_connect(conn)
                    return conn
                else:
                    await self._cond.wait()

    async def _fill_free_pool(self):
        # pylint: disable=no-value-for-parameter
        # iterate over free connections and remove timeouted ones
        n, free = 0, len(self._free)
        while n < free:
            conn = self._free[-1]
            if not conn.open:
                self._free.pop()
            else:
                self._free.rotate(1)
            n += 1

        while self.size < self.maxsize:
            self._acquiring += 1
            try:
                conn = await connect(
                    self._url, loop=self._loop, timeout=self._timeout,
                    **self._conn_kwargs)
                # raise exception if pool is closing
                self._free.append(conn)
                self._cond.notify()
            finally:
                self._acquiring -= 1
        if self._free:
            return

    async def _wakeup(self):
        async with self._cond:
            self._cond.notify()

    def release(self, conn: WSConn) -> asyncio.Future:
        """Release free connection back to the connection pool.
        """
        fut = self._loop.create_future()
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
                asyncio.ensure_future(conn.close())
            else:
                self._free.append(conn)
            fut = asyncio.ensure_future(self._wakeup(), loop=self._loop)
        return fut

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.close()
        await self.wait_closed()


async def create_pool(url=None, *,
                      minsize=1,  # min connections in pool
                      maxsize=10,  # max connections in pool
                      loop=None,
                      timeout=1,  # timeout for closing handshake
                      pool_recycle=-1,  # recycle connection after x messages
                      **kwargs) -> Coroutine[Any, Any, Pool]:
    # pylint: disable=protected-access
    if loop is None:
        loop = asyncio.get_event_loop()

    pool = Pool(url=url, minsize=minsize, maxsize=maxsize, loop=loop,
                timeout=timeout, pool_recycle=pool_recycle,
                **kwargs)
    if minsize > 0:
        async with pool._cond:
            await pool._fill_free_pool()
    return pool
