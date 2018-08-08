# -*- coding: utf-8 -*-
import asyncio
import json
import sys
from functools import partial
from urllib.parse import urlparse

import aiohttp
import async_timeout
import ujson

from jussi.ws.pool import Pool

from .cache import setup_caches
from .typedefs import WebApp
from .upstream import _Upstreams


def setup_listeners(app: WebApp) -> WebApp:
    # pylint: disable=unused-argument, unused-variable
    @app.listener('before_server_start')
    def setup_debug(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_debug', debug=app.config.args.debug,
                    debug_route=app.config.args.monitor_route,
                    when='before_server_start')
        if app.config.args.monitor_route is True or app.config.args.debug is True:
            from jussi.handlers import monitor
            app.add_route(monitor, '/monitor', methods=['GET'])

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
        tcp_connector = aiohttp.TCPConnector()

        aio = dict(session=aiohttp.ClientSession(
            connector=tcp_connector,
            skip_auto_headers=['User-Agent'],
            loop=loop,
            json_serialize=partial(ujson.dumps, ensure_ascii=False),
            headers={'Content-Type': 'application/json'}))
        app.config.aiohttp = aio

    @app.listener('before_server_start')
    async def setup_websocket_connection_pools(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_websocket_connection_pools', when='before_server_start')
        args = app.config.args
        upstream_urls = app.config.upstreams.urls

        pools = dict()
        ws_connect_kwargs = dict(
            max_queue=args.websocket_queue_size,
            max_size=args.websocket_max_msg_size,
            read_limit=args.websocket_read_limit,
            write_limit=args.websocket_write_limit
        )
        for url in upstream_urls:
            if url.startswith('ws'):
                logger.info('creating websocket pool',
                            pool_min_size=args.websocket_pool_minsize,
                            pool_maxsize=args.websocket_pool_maxsize,
                            max_queries_per_conn=0,
                            url=url,
                            **ws_connect_kwargs
                            )
                pools[url] = await Pool(
                    args.websocket_pool_minsize,  # minsize of pool
                    args.websocket_pool_maxsize,  # maxsize of pool
                    0,  # max queries per conn (0 means unlimited)
                    loop,  # event_loop
                    url,  # connection url
                    # all kwargs are passed to websocket connection
                    **ws_connect_kwargs
                )

        # pylint: disable=protected-access
        app.config.websocket_pools = pools

    @app.listener('before_server_start')
    async def setup_caching(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('setup_caching', when='before_server_start')
        args = app.config.args
        cache_group = setup_caches(app, loop)
        app.config.cache_group = cache_group
        app.config.last_irreversible_block_num = 20_000_000
        try:
            lirb = await cache_group.get('last_irreversible_block_num')
            if lirb is not None:
                app.config.last_irreversible_block_num = lirb
        except Exception as e:
            logger.exception('setup_caching error', e=e)
        logger.info('setup_caching',
                    lirb=app.config.last_irreversible_block_num)
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
        if args.statsd_url is not None:
            url = urlparse(args.statsd_url)
            port = url.port or 8125
            from .async_stats import AsyncStatsClient
            app.config.statsd_client = AsyncStatsClient(host=url.hostname,
                                                        port=port,
                                                        prefix='jussi')
            await app.config.statsd_client.init()
            logger.info('setup_statsd',
                        statsd_hostname=url.hostname,
                        statsd_port=port,
                        prefix='jussi',
                        client=app.config.statsd_client)

    @app.listener('after_server_stop')
    async def close_websocket_connection_pools(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('close_websocket_connection_pools', when='after_server_stop')
        pools = app.config.websocket_pools
        for url, pool in pools.items():
            logger.info('closing websocket pool for %s', url)
            pool.terminate()

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
