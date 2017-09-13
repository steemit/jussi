# -*- coding: utf-8 -*-
import asyncio

import aiocache
import aiohttp
import aiojobs
import janus
import statsd
import ujson

import jussi.cache
import jussi.jobs
import jussi.jsonrpc_method_cache_settings
import jussi.jsonrpc_method_upstream_url_settings
import jussi.logging_config
import jussi.serializers
import jussi.stats
import jussi.ws.pool
from jussi.typedefs import WebApp


def setup_listeners(app: WebApp) -> WebApp:

    # pylint: disable=unused-argument, unused-variable
    @app.listener('before_server_start')
    def setup_cache(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('before_server_start -> setup_cache')

        caches_config = jussi.cache.setup_caches(app, loop)
        aiocache.caches.set_config(caches_config)
        active_caches = []
        # caches should be sorted fastest to slowest, ie,
        # [SimpleMemoryCache,RedisCache]
        for cache_alias in sorted(aiocache.caches.get_config().keys()):
            cache = aiocache.caches.create(alias=cache_alias)
            logger.info('before_server_start -> setup_cache caches=%s',
                        cache_alias)
            logger.info(f'{cache}.serializer is {type(cache.serializer)}')
            active_caches.append(cache)
        app.config.aiocaches = aiocache.caches

        app.config.caches = active_caches

    @app.listener('before_server_start')
    def setup_jsonrpc_method_cache_settings(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info(
            'before_server_start -> setup_jsonrpc_method_cache_settings')
        app.config.method_ttls = jussi.jsonrpc_method_cache_settings.TTLS

    @app.listener('before_server_start')
    def setup_jsonrpc_method_url_settings(app: WebApp, loop) -> None:
        logger = app.config.logger
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
        app.config.websocket_pool_kwargs = dict(url=args.steemd_websocket_url,
                                                minsize=args.websocket_pool_minsize,
                                                maxsize=args.websocket_pool_maxsize,
                                                timeout=5
                                                )
        # pylint: disable=protected-access
        app.config.websocket_pool = await jussi.ws.pool._create_pool(**app.config.websocket_pool_kwargs)

    @app.listener('before_server_start')
    async def setup_statsd(app: WebApp, loop) -> None:
        """setup statsd client and queue"""
        logger = app.config.logger
        logger.info('before_server_start -> setup_statsd')
        app.config.statsd_client = statsd.StatsClient()
        stats_queue = janus.Queue(loop=loop)
        app.config.status_queue = stats_queue
        app.config.stats = jussi.stats.QStatsClient(
            q=stats_queue, prefix='jussi')

    # after server start
    @app.listener('after_server_start')
    async def setup_job_scheduler(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_start -> setup_job_scheduler')

        app.config.last_irreversible_block_num = 0
        app.config.scheduler = await aiojobs.create_scheduler()
        await app.config.scheduler.spawn(
            jussi.jobs.get_last_irreversible_block(app=app))
        logger.info(
            'after_server_start -> setup_job_scheduler scheduled jussi.jobs.get_last_irreversible_block'
        )
        await app.config.scheduler.spawn(jussi.jobs.flush_stats(app=app))
        logger.info(
            'after_server_start -> setup_job_scheduler scheduled jussi.jobs.flush_stats'
        )

    # after server stop
    @app.listener('after_server_stop')
    async def stop_job_scheduler(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> stop_job_scheduler')
        await asyncio.shield(app.config.scheduler.close())

    @app.listener('after_server_stop')
    async def close_websocket_connection_pool(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_websocket_connection_pool')
        pool = app.config.websocket_pool
        pool.terminate()
        await asyncio.shield(pool.wait_closed())

    @app.listener('after_server_stop')
    async def close_aiohttp_session(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_aiohttp_session')
        if not app.config.scheduler.closed:
            await asyncio.shield(app.config.scheduler.close())
        session = app.config.aiohttp['session']
        await asyncio.shield(session.close())

    @app.listener('after_server_stop')
    async def close_stats_queue(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_stats_queue')
        if not app.config.scheduler.closed:
            await asyncio.shield(app.config.scheduler.close())
        stats = app.config.stats
        statsd_client = app.config.statsd_client
        await asyncio.shield(stats.final_flush(statsd_client))

    @app.listener('after_server_stop')
    async def close_cache_connections(app: WebApp, loop) -> None:
        logger = app.config.logger
        logger.info('after_server_stop -> close_cache_connections')
        for cache in app.config.caches:
            await cache.close()

    return app
