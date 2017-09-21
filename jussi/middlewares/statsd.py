# -*- coding: utf-8 -*-
import logging
from typing import Optional

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse

from ..errors import ignore_errors_async
from ..upstream import async_exclude_methods
from ..upstream import is_batch_jsonrpc
from ..upstream import stats_key

logger = logging.getLogger(__name__)


@ignore_errors_async
@async_exclude_methods(exclude_http_methods=('GET', ))
async def request_stats(request: HTTPRequest) -> Optional[HTTPResponse]:
    stats = request.app.config.stats
    if is_batch_jsonrpc(sanic_http_request=request):
        stats.incr('jsonrpc.batch_requests')
        for req in request.json:
            key = stats_key(req)
            stats.incr('jsonrpc.requests.%s' % key)
        return
    key = stats_key(request.json)
    stats.incr('jsonrpc.single_requests')
    stats.incr('jsonrpc.requests.%s' % key)
    request['timer'] = stats.timer('jsonrpc.requests.%s' % key)
    request['timer'].start()


# pylint: disable=unused-argument
@ignore_errors_async
async def finalize_request_stats(request: HTTPRequest,
                                 response: HTTPResponse) -> None:
    if 'timer' in request:
        request['timer'].stop()
