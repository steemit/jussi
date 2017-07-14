# -*- coding: utf-8 -*-

import aiohttp
import pygtrie
import ujson
import websockets

import jussi.cache
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

        cache_config = dict()
        cache_config['default_ttl'] = jussi.cache.DEFAULT_TTL
        cache_config['no_cache_ttl'] = jussi.cache.NO_CACHE_TTL
        cache_config['no_expire_ttl'] = jussi.cache.NO_EXPIRE_TTL

        app.config.cache_config = cache_config
        app.config.caches = active_caches

    @app.listener('before_server_start')
    def setup_upstreams(app: WebApp, loop) -> None:
        logger.info('before_server_start -> config_upstreams')
        args = app.config.args

        upstreams = pygtrie.StringTrie(separator='.')

        # steemd methods aren't namespaced so this is the steemd default entry
        upstreams[''] = dict(
            url=args.steemd_websocket_url, ttl=jussi.cache.DEFAULT_TTL)

        upstreams['sbds'] = dict(url=args.sbds_url, ttl=30)

        for m in jussi.cache.METHOD_CACHE_SETTINGS:
            name, url_name, ttl = m
            url = getattr(args, url_name)
            upstreams[name] = dict(url=url, ttl=ttl)

        app.config.upstreams = upstreams

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

    return app
