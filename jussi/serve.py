#!/usr/bin/env python
# -*- coding: utf-8 -*-
import asyncio
import os

import configargparse
import uvloop
from sanic import Sanic

import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
import jussi.sanic_config
from jussi.request.http import HTTPRequest
from jussi.typedefs import WebApp

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


def strtobool(val):
    """Convert a string representation of truth to true (1) or false (0).

    True values are 'y', 'yes', 't', 'true', 'on', and '1'; false values
    are 'n', 'no', 'f', 'false', 'off', and '0'.  Raises ValueError if
    'val' is anything else.
    """
    val = val.lower()
    if val in ('y', 'yes', 't', 'true', 'on', '1'):
        return 1
    elif val in ('n', 'no', 'f', 'false', 'off', '0'):
        return 0
    else:
        raise ValueError("invalid truth value %r" % (val,))


def int_or_none(val):
    if val is None:
        return val
    if val.lower() == 'none':
        return None
    return int(val)


def setup_routes(app: WebApp) -> WebApp:
    app.add_route(jussi.handlers.healthcheck, '/health', methods=['GET', 'HEAD'])
    app.add_route(jussi.handlers.handle_jsonrpc, '/', methods=['POST'])
    return app


def parse_args(args: list = None):
    """parse CLI args and add them to app.config
    """
    parser = configargparse.get_argument_parser()

    # server config
    parser.add_argument('--debug',
                        type=lambda x: bool(strtobool(x)),
                        env_var='JUSSI_DEBUG',
                        default=False)
    parser.add_argument('--monitor_route',
                        type=lambda x: bool(strtobool(x)),
                        env_var='JUSSI_MONITOR_ROUTE',
                        default=True)
    parser.add_argument('--server_host', type=str, env_var='JUSSI_SERVER_HOST',
                        default='0.0.0.0')
    parser.add_argument('--server_port', type=int, env_var='JUSSI_SERVER_PORT',
                        default=9000)
    parser.add_argument('--server_workers', type=int,
                        env_var='JUSSI_SERVER_WORKERS', default=os.cpu_count())
    parser.add_argument('--server_tcp_backlog', type=int,
                        env_var='JUSSI_SERVER_TCP_BACKLOG', default=100)

    parser.add_argument('--jsonrpc_batch_size_limit', type=int,
                        env_var='JUSSI_JSONRPC_BATCH_SIZE_LIMIT', default=50)

    # server websocket pool config
    parser.add_argument('--websocket_pool_minsize', type=int,
                        env_var='JUSSI_WEBSOCKET_POOL_MINSIZE', default=8)
    parser.add_argument('--websocket_pool_maxsize',
                        env_var='JUSSI_WEBSOCKET_POOL_MAXSIZE', type=int,
                        default=8)
    parser.add_argument('--websocket_queue_size',
                        env_var='JUSSI_WEBSOCKET_QUEUE', type=int, default=1)
    parser.add_argument('--websocket_read_limit',
                        env_var='JUSSI_WEBSOCKET_READ_LIMIT', type=int, default=2**16)
    parser.add_argument('--websocket_write_limit',
                        env_var='JUSSI_WEBSOCKET_WRITE_LIMIT', type=int, default=2**16)
    parser.add_argument('--websocket_max_msg_size',
                        env_var='JUSSI_WEBSOCKET_MAX_MESSAGE_SIZE',
                        default=None,
                        type=int_or_none)

    # server version
    parser.add_argument('--source_commit', env_var='SOURCE_COMMIT', type=str,
                        default='')
    parser.add_argument('--docker_tag', type=str, env_var='DOCKER_TAG',
                        default='')

    # upstream config
    parser.add_argument('--upstream_config_file', type=str,
                        env_var='JUSSI_UPSTREAM_CONFIG_FILE',
                        default='DEV_config.json')
    parser.add_argument('--test_upstream_urls',
                        env_var='JUSSI_TEST_UPSTREAM_URLS',
                        type=lambda x: bool(strtobool(x)),
                        default=True)

    # cache config (applies to all caches
    parser.add_argument('--cache_read_timeout', type=float,
                        env_var='JUSSI_CACHE_READ_TIMEOUT', default=1.0)
    parser.add_argument('--cache_test_before_add',
                        type=lambda x: bool(strtobool(x)),
                        env_var='JUSSI_CACHE_TEST_BEFORE_ADD', default=False)

    # redis config
    # redis://[:password]@localhost:6379/0
    parser.add_argument('--redis_url', type=str, env_var='JUSSI_REDIS_URL',
                        help='redis://[:password]@host:6379/0',
                        default=None)

    parser.add_argument('--redis_read_replica_urls', type=str,
                        env_var='JUSSI_REDIS_READ_REPLICA_URLS', default=None,
                        help='redis://[:password]@host:6379/0',
                        nargs='*')

    # statsd statsd://host:port
    parser.add_argument('--statsd_url', type=str, env_var='JUSSI_STATSD_URL',
                        help='statsd://host:port',
                        default=None)

    return parser.parse_args(args=args)


def main():
    args = parse_args()
    # run app
    app = Sanic(__name__,
                log_config=jussi.logging_config.LOGGING,
                request_class=HTTPRequest)
    app.config.from_object(jussi.sanic_config)
    app.config.args = args
    app = jussi.logging_config.setup_logging(app)
    app = setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)

    run_config = dict(
        host=app.config.args.server_host,
        port=app.config.args.server_port,
        workers=app.config.args.server_workers,
        access_log=False,
        debug=app.config.args.debug,
        backlog=app.config.args.server_tcp_backlog)

    app.config.logger.info('app.config', config=app.config)
    app.config.logger.info('app.run', config=run_config)
    app.run(**run_config)


if __name__ == '__main__':
    args = parse_args()
    # run app
    app = Sanic(__name__,
                log_config=jussi.logging_config.LOGGING,
                request_class=HTTPRequest)
    app.config.from_object(jussi.sanic_config)
    app.config.args = args
    app = jussi.logging_config.setup_logging(app)
    app = setup_routes(app)
    app = jussi.middlewares.setup_middlewares(app)
    app = jussi.errors.setup_error_handlers(app)
    app = jussi.listeners.setup_listeners(app)

    run_config = dict(
        host=app.config.args.server_host,
        port=app.config.args.server_port,
        workers=app.config.args.server_workers,
        access_log=False,
        debug=app.config.args.debug,
        backlog=app.config.args.server_tcp_backlog)

    app.config.logger.info('app.config', config=app.config)
    app.config.logger.info('app.run', config=run_config)
    app.run(**run_config)
