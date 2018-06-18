# -*- coding: utf-8 -*-
from ..errors import JsonRpcBatchSizeError
from ..errors import handle_middleware_exceptions
from ..typedefs import HTTPRequest
from ..validators import limit_broadcast_transaction_request


@handle_middleware_exceptions
async def check_limits(request: HTTPRequest) -> None:
    # pylint: disable=no-member
    if request.is_single_jrpc:
        limit_broadcast_transaction_request(request.jsonrpc,
                                            limits=request.app.config.limits)
    elif request.is_batch_jrpc:
        if len(request.jsonrpc) > request.app.config.jsonrpc_batch_size_limit:
            raise JsonRpcBatchSizeError(jrpc_batch_size=len(request.jsonrpc),
                                        jrpc_batch_size_limit=request.app.config.jsonrpc_batch_size_limit)

        _ = [limit_broadcast_transaction_request(r, limits=request.app.config.limits)
             for r in request.jsonrpc
             ]
