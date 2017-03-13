# -*- coding: utf-8 -*-
import os
from collections import defaultdict
import logging
import time
from urllib.parse import urlparse
from urllib.parse import urlunparse
import ujson
import aiohttp

from aiohttp import web

log_level = getattr(logging, os.environ.get('SBDS_LOG_LEVEL', 'INFO'))
logging.basicConfig(level=log_level)
logger = logging.getLogger('jussi')


jsonrpc_error_code_map = {
    'parse_error': {
        'code': -32700,
        'message': 'Parse error'
    },
    'invalid_request': {
        'code': -32600,
        'message': 'Invalid Request'
    },
    'method_not_found': {
        'code': -32601,
        'message': 'Method not found'
    },
    'invalid_params': {
        'code': -32602,
        'message': 'Invalid params'
    },
    'internal_error': {
        'code': -32603,
        'message': 'Internal error'
    },
}


def generate_json_rpc_error(code, data=None):
    error_dict = dict(jsonrpc_error_code_map[code])
    if data:
        error_dict.update(data=data)
    return error_dict


class JSONRPCException(web.HTTPOk):
    def __init__(self, jsonrpc_error_code, req_id=None, data=None):
        req_id = req_id or 0
        content_type = 'application/json'
        json_rpc_error_dict = {
            'jsonrpc': '2.0',
            'id': req_id,
            'error': generate_json_rpc_error(jsonrpc_error_code,
                                             data=data)
        }
        text = ujson.dumps(json_rpc_error_dict)
        super(self, JSONRPCException).__init__(content_type=content_type, text=text)

async def forward(request, url):
    start = time.time()
    async with aiohttp.ClientSession() as session:
        async with session.post(urlunparse(url), data=ujson.dumps(request)) as proxied_request:
            content = await proxied_request.read()
            response = aiohttp.web.Response(body=content, content_type='application/json')
        return response


class MethodRouter(object):
    def __init__(self):
        self._namespaces = {}
        self._default_namespace = {}

    async def do_route(self, request):
        logger.info(request)
        try:
            jsonrpc_request = await request.json(loads=ujson.loads)
            logger.info(jsonrpc_request)
        except Exception as e:
            logger.info(e)
            raise JSONRPCException('parse_error')
        try:
            assert 'id' in jsonrpc_request
            assert 'method' in jsonrpc_request
            assert 'jsonrpc' in jsonrpc_request
            assert jsonrpc_request['jsonrpc'] == '2.0'
        except AssertionError as e:
            logger.info(e)
            raise JSONRPCException('invalid_request')

        forward_url, jsonrpc_request = self.prepare_request(jsonrpc_request)

        try:
            return await forward(jsonrpc_request, forward_url)
        except Exception as e:
            raise JSONRPCException('internal_error')

    def namespace(self, method):
        namespace = method.split('.')[0]
        if namespace in self._namespaces:
            return tuple([namespace, *self._namespaces[namespace]])
        else:
            return self._default_namespace

    def prepare_request(self, jsonrpc_request):
        namespace, url, strip_namespace = self.namespace(jsonrpc_request['method'])
        logger.debug('namespace:%s url%s strip:%s', namespace, url, strip_namespace)

        if strip_namespace:
            jsonrpc_request['method'] = jsonrpc_request['method'].strip('%s.' % namespace)
            logger.debug('stripped namespace %s from method, new method:%s', namespace,
                         jsonrpc_request['method'])

        return url, jsonrpc_request

    def register_upstream(self, namespace, url, strip_namespace=False):
        self._namespaces[namespace] = url, strip_namespace
        logger.debug('registered %s namespace at %s', namespace, url)


    def register_default_upstream(self, namespace, url, strip_namespace=False):
        self._default_namespace = namespace, url, strip_namespace
        logger.debug('registered default %s namespace at %s', namespace, url)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description="jussi reverse proxy server")
    parser.add_argument('--server_port', type=int, default=8080)
    parser.add_argument('--steemd_url', type=urlparse, default='https://steemd.steemitdev.com')
    parser.add_argument('--sbds_url', type=urlparse, default='https://sbds.steemitdev.com')
    args = parser.parse_args()

    chooser = MethodRouter()
    chooser.register_upstream(namespace='sbds', url=args.sbds_url)
    chooser.register_upstream(namespace='steemd', url=args.steemd_url, strip_namespace=True)
    chooser.register_default_upstream(namespace='steemd', url=args.steemd_url, strip_namespace=True)

    app = web.Application()
    app.router.add_post('/', chooser.do_route)
    web.run_app(app, port=args.server_port)
