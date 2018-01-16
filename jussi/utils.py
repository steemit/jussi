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

logger = logging.getLogger(__name__)


# decorators
def async_exclude_methods(
        middleware_func: Optional[Callable] = None,
        exclude_http_methods: Tuple[str] = None) -> Optional[Callable]:
    """Exclude specified HTTP methods from middleware

    Args:
        middleware_func:
        exclude_http_methods:

    Returns:

    """
    if middleware_func is None:
        return functools.partial(
            async_exclude_methods, exclude_http_methods=exclude_http_methods)

    @functools.wraps(middleware_func)
    async def f(request: HTTPRequest) -> Optional[HTTPResponse]:
        if request.method in exclude_http_methods:
            return None
        return await middleware_func(request)
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
        asyncio.ensure_future(middleware_func(request, response))
    return f


def is_batch_jsonrpc(
        jsonrpc_request: JsonRpcRequest = None,
        sanic_http_request: HTTPRequest = None, ) -> bool:
    try:
        return isinstance(jsonrpc_request, list) or isinstance(
            sanic_http_request.json, list)
    except Exception:
        return False


def chunkify(iterable, chunksize=None):
    i = 0
    chunk = []
    for item in iterable:
        chunk.append(item)
        i += 1
        if i == chunksize:
            yield chunk
            i = 0
            chunk = []
    if chunk:
        yield chunk
