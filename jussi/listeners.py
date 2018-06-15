# -*- coding: utf-8 -*-
import json
import sys

import aiohttp

import jussi.logging_config
import jussi.ws.pool
import ujson

from .cache import setup_caches
from .typedefs import WebApp
from .upstream import _Upstreams


def setup_listeners(app: WebApp) -> WebApp:
    # pylint: disable=unused-argument, unused-variable
    @app.listener('before_server_start')
    def setup_debug(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_debug', when='before_server_start')
        loop.set_debug(app.config.args.debug)

    @app.listener('before_server_start')
    def setup_upstreams(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_upstreams', when='before_server_start')
        args = app.config.args
        upstream_config_file = args.upstream_config_file
        with open(upstream_config_file) as f:
            upstream_config = json.load(f)
        try:
            app.config.upstreams = _Upstreams(upstream_config,
                                              validate=args.test_upstream_urls)
        except Exception as e:
            logger.error('Bad upstream in config', e=e)
            sys.exit(127)

    @app.listener('before_server_start')
    def setup_aiohttp_session(app: WebApp, loop) -> None:
        """use one session for http connection pooling
        """
        logger = app.config.logger
        logger.info('setup_aiohttp_session', when='before_server_start')
        aio = dict(session=aiohttp.ClientSession(
            skip_auto_headers=['User-Agent'],
            loop=loop,
            json_serialize=ujson.dumps,
            headers={'Content-Type': 'application/json'}))
        app.config.aiohttp = aio

    @app.listener('before_server_start')
    async def setup_websocket_connection_pools(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_websocket_connection_pools', when='before_server_start')
        args = app.config.args
        upstream_urls = app.config.upstreams.urls
        app.config.websocket_pool_kwargs = dict(
            minsize=args.websocket_pool_minsize,
            maxsize=args.websocket_pool_maxsize,
            timeout=5,
            pool_recycle=args.websocket_pool_recycle,
            max_queue=args.websocket_queue_size)

        pools = dict()
        for url in upstream_urls:
            if url.startswith('ws'):
                logger.info('creating websocket pool', url=url)
                pools[url] = await jussi.ws.pool.create_pool(url=url,
                                                             **app.config.websocket_pool_kwargs)

        # pylint: disable=protected-access
        app.config.websocket_pools = pools

    @app.listener('before_server_start')
    async def setup_caching(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_caching', when='before_server_start')
        args = app.config.args
        cache_group = setup_caches(app, loop)
        app.config.cache_group = cache_group
        lirb = 20_000_000
        try:
            lirb = await cache_group.get('last_irreversible_block_num')
        except Exception as e:
            logger.exception('setup_caching error', e=e)
        app.config.last_irreversible_block_num = lirb
        logger.info('setup_caching', lirb=lirb)
        app.config.cache_read_timeout = args.cache_read_timeout

    @app.listener('before_server_start')
    async def setup_limits(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_limits', when='before_server_start')
        args = app.config.args
        config_file = args.upstream_config_file
        with open(config_file) as f:
            config = json.load(f)
        app.config.limits = config.get('limits', {'accounts_blacklist': set()})

        app.config.jsonrpc_batch_size_limit = args.jsonrpc_batch_size_limit

    @app.listener('before_server_start')
    async def setup_statsd(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_statsd', when='before_server_start')
        args = app.config.args
        app.config.statsd_client = None
        if args.statsd_host is not None:
            from .async_stats import AsyncStatsClient
            app.config.statsd_client = AsyncStatsClient(host=args.statsd_host,
                                                        port=args.statsd_port,
                                                        prefix='jussi')
            await app.config.statsd_client.init()

    @app.listener('after_server_stop')
    async def close_websocket_connection_pools(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('close_websocket_connection_pools', when='after_server_stop')
        pools = app.config.websocket_pools
        for url, pool in pools.items():
            logger.info('terminating websocket pool for %s', url)
            pool.terminate()
            await pool.wait_closed()

    @app.listener('after_server_stop')
    async def close_aiohttp_session(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('close_aiohttp_session', when='after_server_stop')
        session = app.config.aiohttp['session']
        await session.close()

    @app.listener('after_server_stop')
    async def shutdown_caching(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('shutdown_caching', when='after_server_stop')
        cache_group = app.config.cache_group
        await cache_group.close()

    return app
