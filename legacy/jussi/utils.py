# -*- coding: utf-8 -*-
import asyncio
import functools
from typing import Callable
from typing import Optional

import structlog

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse

logger = structlog.get_logger(__name__)


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
