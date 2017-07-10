# -*- coding: utf-8 -*-
import concurrent.futures
import json
import logging
import os
import socket
import time
from functools import partial
from functools import partialmethod
from urllib.parse import urlparse

import certifi
import urllib3
from urllib3.connection import HTTPConnection

logger = logging.getLogger(__name__)


class RPCError(Exception):
    pass


class RPCConnectionError(Exception):
    pass


def chunkify(iterable, chunksize=3000):
    i = 0
    chunk = []
    for item in iterable:
        chunk.append(item)
        i += 1
        if i == chunksize:
            yield chunk
            i = 0
            chunk = []
    if chunk:
        yield chunk


class SimpleSteemAPIClient(object):
    """Simple Steem JSON-HTTP-RPC API

        This class serves as an abstraction layer for easy use of the
        Steem API.

    Args:
      str: url: url of the API server
      urllib3: HTTPConnectionPool url: instance of urllib3.HTTPConnectionPool

    .. code-block:: python

    from sbds.client import SimpleSteemAPIClient
    rpc = SimpleSteemAPIClient("http://domain.com:port")

    any call available to that port can be issued using the instance
    via the syntax rpc.exec_rpc('command', (*parameters*). Example:

    .. code-block:: python

    rpc.exec('info')

    Returns:

    """

    def __init__(self, url=None, **kwargs):
        url = url or os.environ.get('STEEMD_HTTP_URL',
                                    'https://steemd.steemitdev.com')
        self.url = url
        self.hostname = urlparse(url).hostname
        self.return_with_args = kwargs.get('return_with_args', False)
        self.re_raise = kwargs.get('re_raise', False)
        self.max_workers = kwargs.get('max_workers', None)

        num_pools = kwargs.get('num_pools', 10)
        maxsize = kwargs.get('maxsize', 10)
        timeout = kwargs.get('timeout', 60)
        retries = kwargs.get('retries', 30)
        pool_block = kwargs.get('pool_block', False)
        tcp_keepalive = kwargs.get('tcp_keepalive', True)

        if tcp_keepalive:
            socket_options = HTTPConnection.default_socket_options + \
                [(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1), ]
        else:
            socket_options = HTTPConnection.default_socket_options

        self.http = urllib3.poolmanager.PoolManager(
            num_pools=num_pools,
            maxsize=maxsize,
            block=pool_block,
            timeout=timeout,
            retries=retries,
            socket_options=socket_options,
            headers={'Content-Type': 'application/json'},
            cert_reqs='CERT_REQUIRED',
            ca_certs=certifi.where())
        '''
            urlopen(method, url, body=None, headers=None, retries=None,
            redirect=True, assert_same_host=True, timeout=<object object>,
            pool_timeout=None, release_conn=None, chunked=False, body_pos=None,
            **response_kw)
        '''
        self.request = partial(self.http.urlopen, 'POST', url)

        _logger = logging.getLogger('urllib3')

    @staticmethod
    def json_rpc_body(name, *args, as_json=True):
        body_dict = {"method": name, "params": args, "jsonrpc": "2.0", "id": 0}
        if as_json:
            return json.dumps(body_dict, ensure_ascii=False).encode('utf8')
        return body_dict

    def exec(self, name, *args, re_raise=None, return_with_args=None):
        body = SimpleSteemAPIClient.json_rpc_body(name, *args)
        try:
            response = self.request(body=body)
        except Exception as e:
            if re_raise:
                raise e
            else:
                extra = dict(err=e, request=self.request)
                logger.info('Request error', extra=extra)
                self._return(
                    response=None,
                    args=args,
                    return_with_args=return_with_args)
        else:
            if response.status not in tuple([*response.REDIRECT_STATUSES,
                                             200]):
                logger.debug('non 200 response:%s', response.status)

            return self._return(
                response=response,
                args=args,
                return_with_args=return_with_args)

    def _return(self, response=None, args=None, return_with_args=None):
        return_with_args = return_with_args or self.return_with_args

        if not response:
            result = None
        elif response.status != 200:
            result = None
        else:
            try:
                response_json = json.loads(response.data.decode('utf-8'))
            except Exception as e:
                extra = dict(response=response, request_args=args, err=e)
                logger.info('failed to load response', extra=extra)
                result = None
            else:
                if 'error' in response_json:
                    error = response_json['error']
                    error_message = error.get(
                        'detail', response_json['error']['message'])
                    raise RPCError(error_message)

                result = response_json.get('result', None)
        if return_with_args:
            return result, args
        return result

    def exec_multi(self, name, params):
        body_gen = ({
            "method": name,
            "params": [str(i)],
            "jsonrpc": "2.0",
            "id": i
        } for i in params)
        for chunk in chunkify(body_gen):
            batch_json_body = json.dumps(
                chunk, ensure_ascii=False).encode('utf8')
            r = self.request(body=batch_json_body).read()
            print(r)
            batch_response = json.loads(
                self.request(body=batch_json_body).read())
            for i, resp in enumerate(batch_response):
                yield self._return(
                    response=resp,
                    args=batch_json_body[i]['params'],
                    return_with_args=True)

    def exec_batch(self, name, params):
        batch_requests = [{
            "method": name,
            "params": [str(i)],
            "jsonrpc": "2.0",
            "id": i
        } for i in params]
        for chunk in chunkify(batch_requests):
            batch_json_body = json.dumps(chunk).encode()
            r = self.request(body=batch_json_body)
            batch_response = json.loads(r.data.decode())
            for resp in batch_response:
                yield json.dumps(resp)

    def exec_batch_with_futures(self, name, params, max_workers=None):
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=max_workers) as executor:
            futures = []
            for chunk in chunkify(params):
                futures.append(executor.submit(self.exec_batch, name, chunk))

            for future in concurrent.futures.as_completed(futures):
                for item in future.result():
                    yield item

    get_dynamic_global_properties = partialmethod(
        exec, 'get_dynamic_global_properties')

    get_config = partialmethod(exec, 'get_config')

    get_block = partialmethod(exec, 'get_block')

    def last_irreversible_block_num(self):
        return self.get_dynamic_global_properties()[
            'last_irreversible_block_num']

    def head_block_height(self):
        return self.get_dynamic_global_properties()[
            'last_irreversible_block_num']

    def block_height(self):
        return self.get_dynamic_global_properties()[
            'last_irreversible_block_num']

    def block_interval(self):
        return self.get_config()['STEEMIT_BLOCK_INTERVAL']

    def stream(self, start=None, stop=None, interval=None):
        start = start or self.block_height()
        interval = interval or self.block_interval()
        block_num = start
        # pylint: disable=bare-except
        while True:
            current_height = self.block_height()
            if block_num > current_height:
                block_num = current_height
            try:
                block = self.get_block(block_num)
                yield block
            except:
                pass
            else:
                block_num += 1
                if stop:
                    if block_num > stop:
                        break
            time.sleep(interval / 2)
