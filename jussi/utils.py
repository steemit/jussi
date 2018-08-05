# -*- coding: utf-8 -*-
import asyncio
import functools
import os
import signal
from typing import Callable
from typing import Optional

import structlog

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse

logger = structlog.get_logger(__name__)

def stop_server_from_worker():
    """Send SIGTERM signal to the process group

    The sanic server creates a number of worker processes. Calling app.stop()
    from a worker process doesn't stop other workers, nor does the parent
    process spawn a replacement process. Sending SIGTERM to the
    process group will all gracefully terminate all procs.

    If running in the container, runit will restart the server process which
    will create the new worker processes.
    """
    os.killpg(os.getpgid(os.getpid()), signal.SIGTERM)


def async_nowait_middleware(middleware_func: Callable) -> Callable:
    """Execute middlware function asynchronously but don't wait for result

    Args:
        middleware_func:

    Returns:
        middleware_func

    """
    @functools.wraps(middleware_func)
    async def f(request: HTTPRequest, response: Optional[HTTPResponse]=None) -> None:
        asyncio.ensure_future(asyncio.shield(middleware_func(request, response)))
    return f
