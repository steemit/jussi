# -*- coding: utf-8 -*-

from .gzip import decompress_request
from .gzip import compress_response
from .jsonrpc import validate_jsonrpc_request
from .jussi import add_jussi_request_id
from .jussi import add_jussi_response_id
from .caching import get_response
from .caching import cache_response


def setup_middlewares(app):
    logger = app.config.logger
    logger.info('before_server_start -> setup_middlewares')

    # request middleware
    app.request_middleware.append(decompress_request)
    app.request_middleware.append(add_jussi_request_id)
    app.request_middleware.append(validate_jsonrpc_request)
    app.request_middleware.append(get_response)

    # response middlware
    app.response_middleware.append(add_jussi_response_id)
    app.response_middleware.append(cache_response)
    app.response_middleware.append(compress_response)
    return app
