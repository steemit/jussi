# -*- coding: utf-8 -*-

from .jsonrpc import validate_jsonrpc_request
from .jussi import finalize_jussi_response
from .jussi import convert_to_jussi_request
from .caching import get_response
from .caching import cache_response
from .update_block_num import update_last_irreversible_block_num


def setup_middlewares(app):
    logger = app.config.logger
    logger.info('before_server_start -> setup_middlewares')

    # request middleware
    app.request_middleware.append(validate_jsonrpc_request)
    app.request_middleware.append(convert_to_jussi_request)
    app.request_middleware.append(get_response)

    # response middlware
    app.response_middleware.append(finalize_jussi_response)
    app.response_middleware.append(cache_response)
    app.response_middleware.append(update_last_irreversible_block_num)

    logger.info(f'configured request middlewares:{app.request_middleware}')
    logger.info(f'configured response middlewares:{app.response_middleware}')
    return app
