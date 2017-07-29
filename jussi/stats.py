# -*- coding: utf-8 -*-
import logging

from statsd.client import StatsClientBase

logger = logging.getLogger('sanic')

class QStatsClient(StatsClientBase):
    """A sync/async queed client for statsd."""

    def __init__(self, q, stats_per_flush=100, prefix = None):
        """Create a new client."""
        self.q = q
        self.stats_per_flush = stats_per_flush
        self._prefix = prefix

    # pylint: disable=arguments-differ
    def _send(self, data):
        """Send data to statsd."""
        try:
            self.q.sync_q.put_nowait(data)
        except Exception as e:
            # No time for love, Dr. Jones!
            logger.exception('Failed to enqueue stat: %s', e)
    # pylint: enable=arguments-differ

    def add_stats_to_pipeline(self, pipeline):
        # pylint: disable=protected-access
        logger.debug('QStatsClient.add_stats_to_pipeline starting pipeline length: %s', len(pipeline._stats))
        while not self.q.sync_q.empty():
            if len(pipeline._stats) >= self.stats_per_flush:
                logger.info('QStatsClient.stats_per_flush limit of %s reached',self.stats_per_flush )
                break
            stat = self.q.sync_q.get_nowait()
            logger.debug('QStatsClient added %s to pipeline', stat)
            pipeline._stats.append(stat)
            self.q.sync_q.task_done()
        logger.debug('QStatsClient.add_stats_to_pipeline ending pipeline length: %s', len(pipeline._stats))
        return pipeline

    def pipeline(self):
        raise NotImplementedError('No need to call pipeline with this client')
