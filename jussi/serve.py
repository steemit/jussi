# -*- coding: utf-8 -*-
import argparse
import os

import asyncio
from sanic import Sanic

import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
from jussi.typedefs import WebApp

#logger = logging.getLogger('sanic')


def setup_routes(app: WebApp) -> WebApp:
    app.add_route(jussi.handlers.healthcheck, '/', methods=['GET'])
    app.add_route(jussi.handlers.healthcheck, '/health', methods=['GET'])
    app.add_route(
        jussi.handlers.healthcheck,
        '/.well-known/healthcheck.json',
        methods=['GET'])
    app.add_route(jussi.handlers.handle_jsonrpc, '/', methods=['POST'])
    return app


def parse_args(args: list=None):
    """parse CLI args and add them to app.config
    """
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_host', type=str, default='0.0.0.0')
    parser.add_argument('--server_port', type=int, default=9000)
    parser.add_argument('--server_workers', type=int, default=os.cpu_count())
    parser.add_argument(
        '--steemd_websocket_url', type=str, default='wss://steemd.steemit.com')
    parser.add_argument(
        '--sbds_url', type=str, default='https://sbds.steemit.com')
    parser.add_argument('--redis_host', type=str, default=None)
    parser.add_argument('--redis_port', type=int, default=6379)
    parser.add_argument('--redis_namespace', type=str, default='jussi')
    parser.add_argument('--statsd_host', type=str, default='localhost')
    parser.add_argument('--statsd_port', type=int, default=8125)
    parser.add_argument('--statsd_prefix', type=str, default='jussi')
    return parser.parse_args(args=args)


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

    app.config.logger.info('app.run')
    app.run(host=app.config.args.server_host,
            port=app.config.args.server_port,
            log_config=jussi.logging_config.LOGGING)
