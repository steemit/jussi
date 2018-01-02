# -*- coding: utf-8 -*-

import logging

import ujson

from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..utils import async_nowait_middleware
from ..validators import is_get_dynamic_global_properties_request

logger = logging.getLogger(__name__)


@async_nowait_middleware
async def update_last_irreversible_block_num(request: HTTPRequest, response: HTTPResponse) -> None:
    try:
        app = request.app
        jsonrpc_request = request.json
        jsonrpc_response = ujson.loads(response.body)
        if is_get_dynamic_global_properties_request(jsonrpc_request):
            last_irreversible_block_num = jsonrpc_response['result']['last_irreversible_block_num']
            assert last_irreversible_block_num >= app.config.last_irreversible_block_num
            app.config.last_irreversible_block_num = last_irreversible_block_num
            logger.debug(
                f'updated last_irreversible_block_num: {last_irreversible_block_num}')
    except Exception as e:
        logger.info(f'skipping update of last_irreversible_block_num: {e}')
