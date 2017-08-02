# -*- coding: utf-8 -*-
import logging
from typing import Callable

from funcy.decorators import decorator
from statsd.client import StatsClientBase

from jussi.utils import method_urn

logger = logging.getLogger('sanic')


@decorator
async def time_async_jsonrpc_function(call: Callable):
    jrpc = getattr(call, 'jsonrpc_request')
    stat = getattr(call, 'sanic_http_request')
    if stat and jrpc:
        urn = method_urn(jrpc)
        timer = stat('jsonrpc.requests.%s' % urn)
        timer.start()
        result = await call()
        timer.stop()
        return result

class QStatsClient(StatsClientBase):
    """A sync/async queed client for statsd."""

    def __init__(self, q, max_stats_per_flush=10000, prefix = None):
        """Create a new client."""
        self._q = q
        self.max_stats_per_flush = max_stats_per_flush
        self._prefix = prefix

    # pylint: disable=arguments-differ
    def _send(self, data):
        """Send data to statsd."""
        try:
            self._q.sync_q.put_nowait(data)
        except Exception as e:
            # No time for love, Dr. Jones!
            logger.exception('Failed to enqueue stat: %s', e)
    # pylint: enable=arguments-differ

    @property
    def q(self):
        return self._q

    def add_stats_to_pipeline(self, pipeline):
        # pylint: disable=protected-access
        logger.debug('QStatsClient.add_stats_to_pipeline starting pipeline length: %s', len(pipeline._stats))
        while not self._q.sync_q.empty():
            if len(pipeline._stats) >= self.max_stats_per_flush:
                logger.info('QStatsClient.stats_per_flush limit of %s reached',self.max_stats_per_flush )
                break
            stat = self._q.sync_q.get_nowait()
            logger.debug('QStatsClient added %s to pipeline', stat)
            pipeline._stats.append(stat)
            self._q.sync_q.task_done()
        logger.debug('QStatsClient.add_stats_to_pipeline ending pipeline length: %s', len(pipeline._stats))
        return pipeline

    def pipeline(self):
        raise NotImplementedError('No need to call pipeline with this client')

    def flush(self, client):
        with client.pipeline() as pipe:
            self.add_stats_to_pipeline(pipe)

    async def final_flush(self, client):
        with client.pipeline() as pipe:
            self.add_stats_to_pipeline(pipe)
        self._q.close()
        await self._q.wait_closed()
