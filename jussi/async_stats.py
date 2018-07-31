# -*- coding: utf-8 -*-
import asyncio
from collections import deque
from random import random
from typing import List
from typing import Tuple

import structlog
# pylint: disable=no-name-in-module
from cytoolz import sliding_window

# pylint: enable=no-name-in-module

logger = structlog.get_logger('stats')


__all__ = ['AsyncStatsClient']


class DatagramClientProtocol:

    def __init__(self):
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    # pylint: disable=no-self-use
    def error_received(self, exc):
        logger.debug('error received:', e=exc)

    # pylint: disable=unused-argument
    def connection_lost(self, exc):
        logger.info("socket closed, stopping the event loop")
        loop = asyncio.get_event_loop()
        loop.stop()

# pylint: disable=too-many-instance-attributes,too-many-arguments


class AsyncStatsClient:
    """An asynchronous client for statsd."""

    def __init__(self, host: str='127.0.0.1', port: int=8125, prefix: str=None,
                 maxudpsize: int=512, loop=None):
        """Create a new client."""
        self._host = host
        self._port = port
        self._addr = (self._host, self._port)
        self._loop = loop or asyncio.get_event_loop()
        self._transport = None
        self._protocol = None
        self._prefix = prefix
        self._maxudpsize = maxudpsize
        self._stats = deque()
        if prefix is not None:
            prefix = f'{prefix}.'
        else:
            prefix = ''
        self._prefix = prefix

    async def init(self):
        transport, protocol = await self._loop.create_datagram_endpoint(
            DatagramClientProtocol, remote_addr=self._addr)
        self._transport = transport
        self._protocol = protocol

    def timing(self, stat: str, delta: float, rate=1):
        """Send new timing information. `delta` is in milliseconds."""
        self.put(stat, f'{delta:0.6f}|ms', rate)

    def incr(self, stat: str, count=1, rate=1):
        """Increment a stat by `count`."""
        self.put(stat, f'{count}|c', rate)

    def decr(self, stat: str, count=1, rate=1):
        """Decrement a stat by `count`."""
        self.incr(stat, -count, rate)

    def gauge(self, stat: str, value: int, rate=1, delta=False):
        """Set a gauge value."""
        if value < 0 and not delta:
            if rate < 1 and random() > rate:
                return
            self.put(stat, '0|g', 1)
            self.put(stat, f'{value}|g', 1)
        else:
            prefix = '+' if delta and value >= 0 else ''
            self.put(stat, f'{prefix}{value}|g', rate)

    def set(self, stat: str, value, rate=1):
        """Set a set value."""
        self.put(stat, f'{value}|s', rate)

    def put(self, stat: str, value: str, rate: int) -> None:
        """Send data to statsd."""
        if rate < 1:
            if random() > rate:
                return
            else:
                value = f'{value}|@{rate}'
        self._stats.append(f'{self._prefix}{stat}:{value}')

    def from_timings(self, timings: List[Tuple[float, str]]):
        self._stats.extend(
            f'{self._prefix}{t2[1]}:{((t2[0] - t1[0]) * 1000):0.6f}|ms' for t1, t2 in sliding_window(2, timings)
        )

    def serialize_timings(self, timings: List[Tuple[float, str]]) -> List:
        return [f'{self._prefix}{t2[1]}:{((t2[0] - t1[0]) * 1000):0.6f}|ms' for t1,
                t2 in sliding_window(2, timings)]

    def _sendbatch(self, stats: deque = None):
        try:
            stats = stats or self._stats
            data = stats.popleft()
            while stats:
                # Use popleft to preserve the order of the stats.
                stat = stats.popleft()
                if len(stat) + len(data) + 1 >= self._maxudpsize:
                    self._transport.sendto(data.encode('ascii'))
                    data = stat
                else:
                    data += '\n' + stat
            self._transport.sendto(data.encode('ascii'))
        except Exception as e:
            logger.error('statsd error', exc_info=e)

    def __bool__(self):
        return self._transport is not None


def fmt_timings(timings: List[Tuple[float, str]]):
    return [f'{t2[1]}:{((t2[0] - t1[0]) * 1000):0.6f}|ms' for t1, t2 in sliding_window(2, timings)]
