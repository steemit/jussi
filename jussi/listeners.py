# -*- coding: utf-8 -*-

import aiohttp
import ujson
import websockets

import aiojobs
import jussi.cache
import jussi.jobs
import jussi.jsonrpc_method_cache_settings
import jussi.jsonrpc_method_upstream_url_settings
from jussi.typedefs import WebApp


def setup_listeners(app: WebApp) -> WebApp:
    logger = app.config.logger
    # pylint: disable=unused-argument, unused-variable

    @app.listener('before_server_start')
    def setup_cache(app: WebApp, loop) -> None:
        logger.info('before_server_start -> setup_cache')

        caches = jussi.cache.setup_caches(app, loop)
        for cache_alias in caches.get_config().keys():
            logger.info('before_server_start -> setup_cache caches=%s',
                        cache_alias)
        active_caches = [
            caches.get(alias) for alias in caches.get_config().keys()
        ]

        app.config.caches = active_caches

    @app.listener('before_server_start')
    def setup_jsonrpc_method_cache_settings(app: WebApp, loop) -> None:
        logger.info(
            'before_server_start -> setup_jsonrpc_method_cache_settings')
        app.config.method_ttls = jussi.jsonrpc_method_cache_settings.TTLS

    @app.listener('before_server_start')
    def setup_jsonrpc_method_url_settings(app: WebApp, loop) -> None:
        logger.info('before_server_start -> setup_jsonrpc_method_url_settings')
        args = app.config.args
        mapping = {}
        mapping['steemd_default'] = args.steemd_websocket_url
        mapping['sbds_default'] = args.sbds_url

        app.config.upstream_urls = jussi.jsonrpc_method_upstream_url_settings.deref_urls(
            url_mapping=mapping)

    @app.listener('before_server_start')
    def setup_aiohttp_session(app: WebApp, loop) -> None:
        """use one session for http connection pooling
        """
        logger.info('before_server_start -> setup_aiohttp_session')
        aio = dict(session=aiohttp.ClientSession(
            skip_auto_headers=['User-Agent'],
            loop=loop,
            json_serialize=ujson.dumps,
            headers={'Content-Type': 'application/json'}))
        app.config.aiohttp = aio

    @app.listener('before_server_start')
    async def setup_websocket_connection(app: WebApp, loop) -> None:
        """use one ws connection (per worker) to avoid reconnection
        """
        logger.info('before_server_start -> setup_ws_client')
        args = app.config.args
        app.config.websocket_kwargs = dict(
            uri=args.steemd_websocket_url, max_size=int(2e6), max_queue=200)
        app.config.websocket_client = await websockets.connect(
            **app.config.websocket_kwargs)

    # after server start
    @app.listener('after_server_start')
    async def setup_job_scheduler(app: WebApp, loop) -> None:
        logger.info('before_server_start -> setup_job_scheduler')
        app.config.last_irreversible_block_num = 0
        app.config.scheduler = await aiojobs.create_scheduler()
        await app.config.scheduler.spawn(
            jussi.jobs.get_last_irreversible_block(app=app))

    # before server stop
    @app.listener('before_server_stop')
    def close_aiohttp_session(app: WebApp, loop) -> None:
        logger.info('before_server_stop -> close_aiohttp_session')
        session = app.config.aiohttp['session']
        session.close()

    @app.listener('before_server_stop')
    def close_websocket_connection(app: WebApp, loop) -> None:
        logger.info('before_server_stop -> close_aiohttp_session')
        session = app.config.aiohttp['session']
        session.close()

    @app.listener('before_server_stop')
    async def stop_job_scheduler(app: WebApp, loop) -> None:
        logger.info('before_server_stop -> stop_job_scheduler')
        await app.config.scheduler.close()

    return app
