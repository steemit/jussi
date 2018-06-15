# -*- coding: utf-8 -*-
import structlog

from ..utils import async_nowait_middleware
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

logger = structlog.get_logger(__name__)


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
            statsd_client._sendbatch()
        elif request.is_batch_jrpc and statsd_client:
            statsd_client.from_timings(request.timings)
            for r in request.jsonrpc:
                statsd_client.from_timings(r.timings)
            statsd_client._sendbatch()
    except BaseException as e:
        logger.warning('send_stats', e=e)
