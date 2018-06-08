# -*- coding: utf-8 -*-
import logging
from collections import deque
from typing import Callable

from funcy.decorators import decorator
from statsd.client import StatsClientBase
from statsd.client import PipelineBase

logger = logging.getLogger(__name__)


class QStatsClient(StatsClientBase):
    """A sync/async queed client for statsd."""

    def __init__(self, max_stats_per_flush=10000, prefix=None):
        """Create a new client."""
        self._q = deque()
        self.max_stats_per_flush = max_stats_per_flush
        self._prefix = prefix

    # pylint: disable=arguments-differ
    def _send(self, data):
        """Send data to statsd."""
        self._q.append(data)

    # pylint: enable=arguments-differ

    def add_stats_to_pipeline(self, pipeline):
        # pylint: disable=protected-access
        for stat in self._q:
            logger.debug('stat added to pipeline', stat=stat)
            pipeline._stats.append(stat)
            if len(pipeline._stats) >= self.max_stats_per_flush:
                logger.info('QStatsClient.stats_per_flush limit of %s reached',
                            self.max_stats_per_flush)
                break
        return pipeline

    def pipeline(self):
        raise NotImplementedError('No need to call pipeline with this client')

    def flush(self, client):
        with client.pipeline() as pipe:
            pipe._stats = self._q

    def _send_stats(self, stats, client):
        data = stats.popleft()
        while stats:
            # Use popleft to preserve the order of the stats.
            stat = stats.popleft()
            if len(stat) + len(data) + 1 >= client._maxudpsize:
                client._after(data)
                data = stat
            else:
                data += '\n' + stat
        client._after(data)
