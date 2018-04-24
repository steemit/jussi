# -*- coding: utf-8 -*-
import logging
import random
import time

from ..errors import handle_middleware_exceptions
from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse

from ..validators import is_valid_broadcast_transaction_request

logger = logging.getLogger(__name__)
request_logger = logging.getLogger('jussi_request')


@handle_middleware_exceptions
async def check_limits(request: HTTPRequest) -> None:
    # pylint: disable=no-member

    if request.method == 'POST':

        jsonrpc_request = request.json
        if isinstance(jsonrpc_request, dict):
            assert is_valid_broadcast_transaction_request(
                jsonrpc_request, limits=request.app.config.limits)

        elif isinstance(jsonrpc_request, list):
            for single_jsonrpc_request in jsonrpc_request:
                assert is_valid_broadcast_transaction_request(jsonrpc_request,
                                                              limits=request.app.config.limits)
