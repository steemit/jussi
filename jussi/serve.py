# -*- coding: utf-8 -*-
import os

import configargparse
from sanic import Sanic

import jussi.errors
import jussi.handlers
import jussi.listeners
import jussi.logging_config
import jussi.middlewares
from jussi.typedefs import WebApp

STEEMIT_MAX_BLOCK_SIZE = 393_216_000
REQUEST_MAX_SIZE = STEEMIT_MAX_BLOCK_SIZE + 1000


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


def setup_routes(app: WebApp) -> WebApp:
    app.add_route(jussi.handlers.healthcheck, '/health', methods=['GET'])
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
    parser.add_argument('--server_host', type=str, env_var='JUSSI_SERVER_HOST',
                        default='0.0.0.0')
    parser.add_argument('--server_port', type=str, env_var='JUSSI_SERVER_PORT',
                        default=9000)
    parser.add_argument('--server_workers', type=int,
                        env_var='JUSSI_SERVER_WORKERS', default=os.cpu_count())
    parser.add_argument('--REQUEST_MAX_SIZE', env_var='JUSSI_REQUEST_MAX_SIZE',
                        type=int,
                        default=6_000_000)
    parser.add_argument('--REQUEST_TIMEOUT', type=int,
                        env_var='JUSSI_REQUEST_TIMEOU?T', default=5)
    parser.add_argument('--KEEP_ALIVE', type=lambda x: bool(strtobool(x)),
                        env_var='JUSSI_KEEP_ALIVE', default=True)

    # server websocket pool config
    parser.add_argument('--websocket_pool_minsize', type=int,
                        env_var='JUSSI_WEBSOCKET_POOL_MINSIZE', default=8)
    parser.add_argument('--websocket_pool_maxsize',
                        env_var='JUSSI_WEBSOCKET_POOL_MAXSIZE', type=int,
                        default=8)
    parser.add_argument('--websocket_queue_size',
                        env_var='JUSSI_WEBSOCKET_QUEUE', type=int, default=1)
    parser.add_argument('--websocket_pool_recycle',
                        env_var='JUSSI_WEBSOCKET_POOL_RECYCLE', type=int,
                        default=-1)

    # server version
    parser.add_argument('--source_commit', env_var='SOURCE_COMMIT', type=str,
                        default='')
    parser.add_argument('--docker_tag', type=str, env_var='DOCKER_TAG',
                        default='')

    # upstream config
    parser.add_argument('--upstream_config_file', type=str,
                        env_var='JUSSI_UPSTREAM_CONFIG_FILE',
                        default='PROD_UPSTREAM_CONFIG.json')
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

    parser.add_argument('--redis_host', type=str, env_var='JUSSI_REDIS_HOST',
                        default=None)
    parser.add_argument('--redis_port', type=int, env_var='JUSSI_REDIS_PORT',
                        default=6379)
    parser.add_argument('--redis_pool_minsize', type=int,
                        env_var='JUSSI_REDIS_POOL_MINSIZE', default=1)
    parser.add_argument('--redis_pool_maxsize', type=int,
                        env_var='JUSSI_REDIS_POOL_MAXSIZE', default=30)
    parser.add_argument('--redis_read_replica_hosts', type=str,
                        env_var='JUSSI_REDIS_READ_REPLICA_HOSTS', default=None,
                        nargs='*')

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
