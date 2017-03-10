# -*- coding: utf-8 -*-
import logging
import time
import ujson
import aiohttp
from aiohttp import web

logging.basicConfig()
logger = logging.getLogger(__name__)

async def hello(request):
    return web.Response(text="Hello, world")

async def forward(request, host, port):
    start = time.time()
    host_and_port = "%s:%d" % (host, port)
    async with aiohttp.ClientSession() as session:
        async with session.post('https://%s' % host_and_port, data=request.read()) as proxied_request:
            logger.info('opened backend request in %d ms' % ((time.time() - start) * 1000))
            content = await proxied_request.read()
            response = aiohttp.web.Response(body=content)
        logger.info('finished sending content in %d ms' % ((time.time() - start) * 1000,))
        return response

class MethodRouter:
    def __init__(self):
        self._namespaces = {}
        self._default_namespace = 'steemd'

    async def do_route(self, request):
        jsonrpc_request = await request.json(loads=ujson.loads)
        jsonrpc_method = jsonrpc_request['method']
        namespace = jsonrpc_method.split('.')[0]
        handler = self._namespaces.get(namespace, self._default_namespace)
        return await handler(request)

    def register_upstream(self, handler, namespace=None):
        if namespace is None:
            self._default_namespace = handler
        else:
            self._namespaces[namespace] = handler


async def handle_sbds(request):
    # do sbds handling
    return await forward(request, 'sbds.steemitdev.com', 443)


async def handle_steemd(request):
    # do steemd handling
    return await forward(request, 'steemd.steemitdev.com', 443)

chooser = MethodRouter()
chooser.register_upstream(handle_sbds, 'sbds')
chooser.register_upstream(handle_steemd)

app = web.Application()
app.router.add_post('/', chooser.do_route)

if __name__ == '__main__':
    web.run_app(app)