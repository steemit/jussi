# -*- coding: utf-8 -*-
from asyncio.tasks import Task

import structlog

from ..utils import async_nowait_middleware
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

logger = structlog.get_logger(__name__)

# pylint: disable=no-member,pointless-statement,protected-access


async def init_stats(request: HTTPRequest) -> None:

    try:
        statsd_client = getattr(request.app.config, 'statsd_client', None)
        if not statsd_client:
            return
        request.jsonrpc
        # statsd_client.gauge('tasks',len(Task.all_tasks()))
        if request.is_single_jrpc:
            statsd_client.incr('jrpc.inflight')
        elif request.is_batch_jrpc and statsd_client:
            _ = [statsd_client.incr('jrpc.inflight') for r in range(len(request.json))]

    except BaseException as e:
        logger.warning('send_stats', e=e)

# pylint: disable=unused-argument


@async_nowait_middleware
async def send_stats(request: HTTPRequest,
                     response: HTTPResponse) -> None:
    # pylint: disable=bare-except
    try:
        statsd_client = getattr(request.app.config, 'statsd_client', None)
        if not statsd_client:
            return
        if request.is_single_jrpc:
            statsd_client.from_timings(request.timings)
            statsd_client.from_timings(request.jsonrpc.timings)
            statsd_client.decr('jrpc.inflight')
            statsd_client.gauge('tasks', len(Task.all_tasks()))
            statsd_client._sendbatch()
        elif request.is_batch_jrpc and statsd_client:
            statsd_client.from_timings(request.timings)
            for r in request.jsonrpc:
                statsd_client.from_timings(r.timings)
                statsd_client.decr('jrpc.inflight')
            statsd_client._sendbatch()
    except BaseException as e:
        logger.warning('send_stats', e=e)
