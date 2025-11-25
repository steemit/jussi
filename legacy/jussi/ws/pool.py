# -*- coding: utf-8 -*-
import asyncio

import structlog
# pylint: disable=no-name-in-module
from websockets import WebSocketClientProtocol as WSConn
from websockets import connect as websockets_connect

# pylint: enable=no-name-in-module
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


# pylint: disable=protected-access
class PoolConnectionProxy:
    __slots__ = ('_con', '_holder')

    def __init__(self, holder: 'PoolConnectionHolder',
                 con: WSConn):
        self._con = con
        self._holder = holder

    def __getattr__(self, attr):
        # Proxy all unresolved attributes to the wrapped Connection object.
        return getattr(self._con, attr)

    def send(self, *args, **kwargs) -> None:
        return self._con.send(*args, **kwargs)

    def recv(self) -> bytes:
        return self._con.recv()

    def terminate(self) -> None:
        self._holder.terminate()

    async def close(self):
        return await self._holder.close()


class PoolConnectionHolder:
    __slots__ = ('_con',
                 '_pool',
                 '_proxy',
                 '_max_queries',
                 '_in_use',
                 '_queries',
                 '_timeout'
                 )

    def __init__(self, pool, *, max_queries: int):

        self._pool = pool
        self._con = None  # type: WSConn
        self._max_queries = max_queries
        self._in_use = None  # type: asyncio.Future
        self._proxy = None
        self._timeout = None
        self._queries = 0

    async def connect(self):
        if self._con is not None:
            raise ValueError(
                'PoolConnectionHolder.connect() called while another '
                'connection already exists')
        self._con = await self._pool._get_new_connection()

    async def acquire(self) -> PoolConnectionProxy:
        if self._con is None or not self._con.open:
            self._con = None
            await self.connect()
        self._in_use = self._pool._loop.create_future()
        self._proxy = PoolConnectionProxy(self, self._con)
        return self._proxy

    async def release(self, timeout: int=None):
        if self._in_use is None:
            raise ValueError(
                'PoolConnectionHolder.release() called on '
                'a free connection holder')

        if self._con.closed:
            # When closing, pool connections perform the necessary
            # cleanup, so we don't have to do anything else here.
            return

        self._timeout = None

        if self._max_queries and self._queries >= self._max_queries:
            # The connection has reached its maximum utilization limit,
            # so close it.  Connection.close() will call _release().
            await self._con.close(timeout=timeout)
            return

        # Free this connection holder and invalidate the
        # connection proxy.
        self._release()

    async def wait_until_released(self):
        if self._in_use is None:
            return
        else:
            await self._in_use

    async def close(self):
        if self._con is not None:
            # Connection.close() will call _release_on_close() to
            # finish holder cleanup.
            await self._con.close()

    def terminate(self):
        if self._con is not None:
            # call _release_on_close() to
            # finish holder cleanup.
            self._con.fail_connection()
            self._release_on_close()

    def _release_on_close(self):
        self._release()
        self._con = None

    def _release(self):
        """Release this connection holder."""
        if self._in_use is None:
            # The holder is not checked out.
            return

        if not self._in_use.done():
            self._in_use.set_result(None)
        self._in_use = None

        # Put ourselves back to the pool queue.
        self._pool._queue.put_nowait(self)

# pylint: disable=too-many-instance-attributes,too-many-arguments,protected-access


class Pool:
    """A connection pool.
    Connection pool can be used to manage a set of connections to an upstream.
    Connections are first acquired from the pool, then used, and then released
    back to the pool.
    """

    __slots__ = ('_queue',
                 '_loop',
                 '_minsize',
                 '_maxsize',
                 '_connect_url',
                 '_connect_kwargs',
                 '_holders',
                 '_initialized',
                 '_closing',
                 '_closed')

    def __init__(self,
                 pool_min_size: int,
                 pool_max_size: int,
                 pool_max_queries: int,
                 pool_loop,
                 connect_url: str,
                 **connect_kwargs):

        if pool_loop is None:
            pool_loop = asyncio.get_event_loop()
        self._loop = pool_loop

        if pool_max_size <= 0:
            raise ValueError('max_size is expected to be greater than zero')

        if pool_min_size < 0:
            raise ValueError(
                'min_size is expected to be greater or equal to zero')

        if pool_min_size > pool_max_size:
            raise ValueError('min_size is greater than max_size')

        if pool_max_queries < 0:
            raise ValueError('max_queries is expected to be greater than or equal zero')

        self._minsize = pool_min_size
        self._maxsize = pool_max_size

        self._holders = []
        self._initialized = False
        self._queue = asyncio.LifoQueue(loop=self._loop)

        self._closing = False
        self._closed = False

        self._connect_url = connect_url
        self._connect_kwargs = connect_kwargs

        for _ in range(pool_max_size):
            ch = PoolConnectionHolder(self, max_queries=pool_max_queries)
            self._holders.append(ch)
            self._queue.put_nowait(ch)

    async def _async__init__(self):
        if self._initialized:
            return
        if self._closed:
            raise ValueError('pool is closed')

        if self._minsize:
            # Since we use a LIFO queue, the first items in the queue will be
            # the last ones in `self._holders`.  We want to pre-connect the
            # first few connections in the queue, therefore we want to walk
            # `self._holders` in reverse.

            if self._minsize > 1:
                connect_tasks = []
                for i, ch in enumerate(reversed(self._holders)):
                    if i >= self._minsize:
                        break
                    connect_tasks.append(ch.connect())
                await asyncio.gather(*connect_tasks, loop=self._loop)
        self._initialized = True
        return self

    async def _get_new_connection(self) -> WSConn:
        # First connection attempt on this pool.
        logger.debug('spawning new ws conn')
        return await websockets_connect(self._connect_url, loop=self._loop,
                                        **self._connect_kwargs)

    async def acquire(self, timeout: int=None) -> PoolConnectionProxy:
        async def _acquire_impl(timeout=None) -> PoolConnectionProxy:
            ch = await self._queue.get()  # type: PoolConnectionHolder
            self._queue.task_done()
            try:
                proxy = await ch.acquire()  # type: # type: PoolConnectionProxy
            except Exception:
                self._queue.put_nowait(ch)
                raise
            else:
                # Record the timeout, as we will apply it by default
                # in release().
                ch._timeout = timeout
                return proxy

        if self._closing:
            raise ValueError('pool is closing')
        if not self._initialized:
            raise ValueError('pool is not initialized')
        if self._closed:
            raise ValueError('pool is closed')

        if timeout is None:
            return await _acquire_impl()
        else:
            return await asyncio.wait_for(
                _acquire_impl(), timeout=timeout, loop=self._loop)

    async def release(self, connection: PoolConnectionProxy, *, timeout: int=None):
        """Release a connection back to the pool.
        """
        if connection._con is None:
            # Already released, do nothing.
            return
        if not self._initialized:
            raise ValueError('pool is not initialized')
        if self._closed:
            raise ValueError('pool is closed')

        ch = connection._holder
        if timeout is None:
            timeout = ch._timeout

        # Use asyncio.shield() to guarantee that task cancellation
        # does not prevent the connection from being returned to the
        # pool properly.
        return await asyncio.shield(ch.release(timeout), loop=self._loop)

    async def close(self):
        """Attempt to gracefully close all connections in the pool.
        Wait until all pool connections are released, close them and
        shut down the pool.  If any error (including cancellation) occurs
        in ``close()`` the pool will terminate by calling
        :meth:`Pool.terminate() <pool.Pool.terminate>`.
        It is advisable to use :func:`python:asyncio.wait_for` to set
        a timeout.

        now waits until all pool connections are released
            before closing them and the pool.  Errors raised in ``close()``
            will cause immediate pool termination.
        """
        if self._closed:
            return
        if not self._initialized:
            raise ValueError('pool is not initialized')
        if self._closed:
            raise ValueError('pool is closed')

        self._closing = True

        try:
            release_coros = [
                ch.wait_until_released() for ch in self._holders]
            await asyncio.gather(*release_coros, loop=self._loop)

            close_coros = [
                ch.close() for ch in self._holders]
            await asyncio.gather(*close_coros, loop=self._loop)

        except Exception:
            self.terminate()
            raise

        finally:
            self._closed = True
            self._closing = False

    def terminate(self):
        """Terminate all connections in the pool."""
        if self._closed:
            return
        if not self._initialized:
            raise ValueError('pool is not initialized')
        if self._closed:
            raise ValueError('pool is closed')
        for ch in self._holders:
            ch.terminate()
        self._closed = True

    def __await__(self):
        return self._async__init__().__await__()
