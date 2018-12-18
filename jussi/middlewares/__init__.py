# -*- coding: utf-8 -*-

from .jussi import initialize_jussi_request
from .jussi import finalize_jussi_response
from .limits import check_limits
from .caching import get_response
from .caching import cache_response
from .update_block_num import update_last_irreversible_block_num
from .statsd import send_stats
from .statsd import log_stats
from .statsd import init_stats


def setup_middlewares(app):
    logger = app.config.logger
    logger.info('setup_middlewares', when='before_server_start')

    # request middleware
    app.request_middleware.append(initialize_jussi_request)
    app.request_middleware.append(init_stats)
    app.request_middleware.append(check_limits)
    app.request_middleware.append(get_response)

    # response middlware
    app.response_middleware.append(finalize_jussi_response)
    app.response_middleware.append(update_last_irreversible_block_num)
    app.response_middleware.append(cache_response)

    if app.config.args.statsd_url is not None:
        app.response_middleware.append(send_stats)
    elif app.config.args.debug:
        app.response_middleware.append(log_stats)

    logger.info('configured request middlewares', middlewares=app.request_middleware)
    logger.info('configured response middlewares', middlewares=app.response_middleware)
    return app
