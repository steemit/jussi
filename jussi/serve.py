# -*- coding: utf-8 -*-
import argparse
import os

from distutils.util import strtobool

from sanic import Sanic

import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
from jussi.typedefs import WebApp

STEEMIT_MAX_BLOCK_SIZE = 393216000
REQUEST_MAX_SIZE = STEEMIT_MAX_BLOCK_SIZE + 1000


def setup_routes(app: WebApp) -> WebApp:
    app.add_route(jussi.handlers.healthcheck, '/health', methods=['GET'])
    app.add_route(jussi.handlers.handle_jsonrpc, '/', methods=['POST'])
    return app


def parse_args(args: list = None):
    """parse CLI args and add them to app.config
    """
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")

    # server config
    parser.add_argument('--debug',
                        type=lambda x: bool(strtobool(x)),
                        default=False)
    parser.add_argument('--server_host', type=str, default='0.0.0.0')
    parser.add_argument('--server_port', type=int, default=9000)
    parser.add_argument('--server_workers', type=int, default=os.cpu_count())
    parser.add_argument('--REQUEST_MAX_SIZE', type=int,
                        default=REQUEST_MAX_SIZE)
    parser.add_argument('--REQUEST_TIMEOUT', type=int, default=5)
    parser.add_argument('--KEEP_ALIVE', type=bool, default=True)

    # server websocket pool config
    parser.add_argument('--websocket_pool_minsize', type=int, default=0)
    parser.add_argument('--websocket_pool_maxsize', type=int, default=5)
    parser.add_argument('--websocket_queue_size', type=int, default=1)
    parser.add_argument('--websocket_pool_recycle', type=int, default=-1)

    # server version
    parser.add_argument('--source_commit', type=str, default='')
    parser.add_argument('--docker_tag', type=str, default='')

    # upstream config
    parser.add_argument('--upstream_config_file', type=str,
                        default='PROD_UPSTREAM_CONFIG.json')
    parser.add_argument('--test_upstream_urls',
                        type=lambda x: bool(strtobool(x)),
                        default=True)
    # redis config
    parser.add_argument('--redis_host', type=str, default=None)
    parser.add_argument('--redis_port', type=int, default=6379)
    parser.add_argument('--redis_namespace', type=str, default='jussi')

    return parser.parse_args(args=args)


def main():
    args = parse_args()
    # run app
    app = Sanic(__name__)
    app.config.args = args
    app = jussi.logging_config.setup_logging(app)
    app = setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)

    run_config = dict(
        host=app.config.args.server_host,
        port=app.config.args.server_port,
        log_config=jussi.logging_config.LOGGING,
        workers=app.config.args.server_workers,
        debug=app.config.args.debug)

    app.config.logger.info(f'app.run({run_config})')
    app.run(**run_config)


if __name__ == '__main__':
    args = parse_args()
    # run app
    app = Sanic(__name__)
    app.config.args = args
    app = jussi.logging_config.setup_logging(app)
    app = setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)

    run_config = dict(
        host=app.config.args.server_host,
        port=app.config.args.server_port,
        log_config=jussi.logging_config.LOGGING,
        workers=app.config.args.server_workers,
        debug=app.config.args.debug)

    app.config.logger.info(f'app.run({run_config})')
    app.run(**run_config)
