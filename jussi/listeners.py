# -*- coding: utf-8 -*-

import aiohttp
import ujson

import jussi.jsonrpc_method_upstream_url_settings
import jussi.logging_config
import jussi.ws.pool

from .cache import setup_caches
from .typedefs import WebApp


def setup_listeners(app: WebApp) -> WebApp:
    # pylint: disable=unused-argument, unused-variable
    @app.listener('before_server_start')
    def setup_jsonrpc_method_url_settings(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('before_server_start -> setup_jsonrpc_method_url_settings')
        args = app.config.args
        mapping = {'steemd_default': args.upstream_steemd_url,
                   'sbds_default': args.upstream_sbds_url}
        app.config.upstream_urls = jussi.jsonrpc_method_upstream_url_settings.deref_urls(
            url_mapping=mapping)

    @app.listener('before_server_start')
    def setup_aiohttp_session(app: WebApp, loop) -> None:
        """use one session for http connection pooling
        """
        logger = app.config.logger
        logger.info('before_server_start -> setup_aiohttp_session')
        aio = dict(session=aiohttp.ClientSession(
            skip_auto_headers=['User-Agent'],
            loop=loop,
            json_serialize=ujson.dumps,
            headers={'Content-Type': 'application/json'}))
        app.config.aiohttp = aio

    @app.listener('before_server_start')
    async def setup_websocket_connection_pool(app: WebApp, loop) -> None:

        logger = app.config.logger
        logger.info('before_server_start -> setup_websocket_connection_pool')
        args = app.config.args
        app.config.websocket_pool_kwargs = dict(url=args.upstream_steemd_url,
                                                minsize=args.websocket_pool_minsize,
                                                maxsize=args.websocket_pool_maxsize,
                                                timeout=5
                                                )
        # pylint: disable=protected-access
        app.config.websocket_pool = await jussi.ws.pool._create_pool(**app.config.websocket_pool_kwargs)

    @app.listener('before_server_start')
    async def setup_caching(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('before_server_start -> setup_caching')
        cache_group = setup_caches(app, loop)
        app.config.cache_group = cache_group

    @app.listener('after_server_stop')
    async def close_websocket_connection_pool(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_websocket_connection_pool')
        pool = app.config.websocket_pool
        pool.terminate()
        await pool.wait_closed()

    @app.listener('after_server_stop')
    async def close_aiohttp_session(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_aiohttp_session')
        session = app.config.aiohttp['session']
        await session.close()

    @app.listener('after_server_stop')
    async def shutdown_caching(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> shutdown_caching')
        cache_group = app.config.cache_group
        await cache_group.close()

    return app
