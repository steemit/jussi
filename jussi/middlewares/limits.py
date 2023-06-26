# -*- coding: utf-8 -*-
from typing import Optional

from ..errors import JsonRpcBatchSizeError
from ..errors import JsonRpcError
from ..errors import JussiAccountHistoryLimitsError
from ..typedefs import HTTPRequest
from ..typedefs import HTTPResponse
from ..validators import limit_broadcast_transaction_request
from ..validators import limit_account_history_count_request


async def check_limits(request: HTTPRequest) -> Optional[HTTPResponse]:
    # pylint: disable=no-member
    try:
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
    except JsonRpcError as e:
        e.add_http_request(http_request=request)
        return e.to_sanic_response()
    except Exception as e:
        return JsonRpcError(http_request=request,
                            exception=e).to_sanic_response()

# This is a temporary way to improve the ahnode backend perform
async def account_history_limit(request: HTTPRequest) -> Optional[HTTPResponse]:
    # pylint: disable=no-member
    if 'account_history_limit' in request.app.config.limits:
        limits = request.app.config.limits['account_history_limit']
    else:
        limits = 100
    try:
        if request.is_single_jrpc:
            limit_account_history_count_request(request.jsonrpc,
                                                limits=limits)
        elif request.is_batch_jrpc:
            _ = [limit_account_history_count_request(r, limits=limits)
                 for r in request.jsonrpc
                 ]
    except JussiAccountHistoryLimitsError as e:
        e.add_http_request(http_request=request)
        return e.to_sanic_response()
    except Exception as e:
        return JsonRpcError(http_request=request,
                            exception=e).to_sanic_response()

