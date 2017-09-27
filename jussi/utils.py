# -*- coding: utf-8 -*-
import functools
import logging
from typing import Callable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from funcy.decorators import Call
from funcy.decorators import decorator

from jussi.typedefs import HTTPRequest
from jussi.typedefs import HTTPResponse
from jussi.typedefs import JsonRpcRequest
from jussi.typedefs import SingleJsonRpcResponse

logger = logging.getLogger(__name__)


# decorators
def async_exclude_methods(
        middleware_func: Optional[Callable]=None,
        exclude_http_methods: Tuple[str]=None) -> Optional[Callable]:
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
            return
        return await middleware_func(request)

    return f


@decorator
async def async_retry(call: Call, tries: int, errors: Union[List, Tuple, Exception]=Exception) -> Optional[SingleJsonRpcResponse]:
    """Makes decorated async function retry up to tries times.
       Retries only on specified errors.
    """
    if isinstance(errors, list):
        # because `except` does not catch exceptions from list
        errors = tuple(errors)

    for attempt in range(tries):
        try:
            return await call()
        # pylint: disable=catching-non-exception
        except errors as e:
            logger.warning(
                f'fetch upstream attempt {attempt+1}/{tries} error:{e}, retyring')
            # Reraise error on last attempt
            if attempt + 1 == tries:
                logger.error(f'fetch failed after {tries} attempts')
                raise


def is_batch_jsonrpc(
        jsonrpc_request: JsonRpcRequest=None,
        sanic_http_request: HTTPRequest=None, ) -> bool:
    try:
        return isinstance(jsonrpc_request, list) or isinstance(
            sanic_http_request.json, list)
    except Exception as e:
        logger.debug(f'is_batch_response exception:{e}')
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
