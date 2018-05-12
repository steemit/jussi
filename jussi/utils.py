# -*- coding: utf-8 -*-
import asyncio
import functools
import logging
from typing import Callable
from typing import Optional
from typing import Tuple

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcRequest

import structlog
logger = structlog.get_logger(__name__)


# decorators
def async_include_methods(
        middleware_func: Optional[Callable] = None,
        include_http_methods: Tuple[str] = None) -> Optional[Callable]:
    """Include specified HTTP methods from middleware

    Args:
        middleware_func:
        exclude_http_methods:

    Returns:

    """
    if middleware_func is None:
        return functools.partial(
            async_include_methods, include_http_methods=include_http_methods)

    @functools.wraps(middleware_func)
    async def f(*args, **kwargs) -> Optional[HTTPResponse]:
        try:
            request = args[0]
            if request.method not in include_http_methods:
                return None
            return await middleware_func(*args, **kwargs)
        except Exception:
            logger.exception('async_include error')

    return f


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


def is_batch_jsonrpc(
        jsonrpc_request: JsonRpcRequest = None,
        sanic_http_request: HTTPRequest = None, ) -> bool:
    try:
        return isinstance(jsonrpc_request, list) or isinstance(
            sanic_http_request.json, list)
    except Exception:
        return False
