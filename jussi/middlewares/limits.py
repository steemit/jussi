# -*- coding: utf-8 -*-
from ..errors import JsonRpcBatchSizeError
from ..errors import handle_middleware_exceptions
from ..request import JussiJSONRPCRequest
from ..typedefs import HTTPRequest
from ..validators import limit_broadcast_transaction_request


@handle_middleware_exceptions
async def check_limits(request: HTTPRequest) -> None:
    # pylint: disable=no-member

    if request.method == 'POST':
        jsonrpc_request = request.json
        if isinstance(jsonrpc_request, JussiJSONRPCRequest):
            limit_broadcast_transaction_request(jsonrpc_request,
                                                limits=request.app.config.limits)

        elif isinstance(jsonrpc_request, list):
            if len(jsonrpc_request) > request.app.config.jsonrpc_batch_size_limit:
                raise JsonRpcBatchSizeError(jrpc_batch_size=len(jsonrpc_request),
                                            jrpc_batch_size_limit=request.app.config.jsonrpc_batch_size_limit)

            for single_jsonrpc_request in jsonrpc_request:
                limit_broadcast_transaction_request(single_jsonrpc_request,
                                                    limits=request.app.config.limits)
