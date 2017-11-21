# -*- coding: utf-8 -*-
import functools
import logging
from typing import Callable
from typing import Optional
from typing import Tuple

from funcy.decorators import Call
from funcy.decorators import decorator

from .typedefs import HTTPRequest
from .typedefs import HTTPResponse
from .typedefs import JsonRpcRequest
from .typedefs import SingleJsonRpcResponse
from .upstream.urn import urn_parts as get_urn_parts
from .validators import is_get_dynamic_global_properties_request

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


@decorator
async def async_retry(call: Call, tries: int) -> Optional[SingleJsonRpcResponse]:
    """Makes decorated async function retry up to tries times.
       Retries only on specified errors.
    """
    parts = get_urn_parts(call.jsonrpc_request)
    if parts.api == 'network_broadcast_api':
        return await call()
    for attempt in range(tries):
        # pylint: disable=catching-non-exception
        try:
            logger.debug(f'fetch upstream attempt {attempt+1}/{tries}')
            return await call()
        except Exception as e:
            logger.info(
                f'fetch upstream attempt {attempt+1}/{tries}, retyring')
            # Reraise error on last attempt
            if attempt + 1 == tries:
                logger.exception(f'fetch failed after {tries} attempts')
                raise e


@decorator
async def update_last_irreversible_block_num(call: Call) -> None:
    try:
        json_response = await call()
    except Exception as e:
        raise e
    try:
        if is_get_dynamic_global_properties_request(call.jsonrpc_request):
            last_irreversible_block_num = json_response['result'][
                'last_irreversible_block_num']
            assert isinstance(last_irreversible_block_num, int)
            assert last_irreversible_block_num > 15_500_000
            app = call.sanic_http_request.app
            app.config.last_irreversible_block_num = last_irreversible_block_num
            logger.info(
                f'updated last_irreversible_block_num: {last_irreversible_block_num}')
    except Exception as e:
        logger.info(f'skipping update of last_irreversible_block_num: {e}')
    return json_response


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
