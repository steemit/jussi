# -*- coding: utf-8 -*-
# pylint: disable=all
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


CORRECT_BATCH_TEST_RESPONSE = '''
[{"id":1,"result":{"previous":"000000b0c668dad57f55172da54899754aeba74b","timestamp":"2016-03-24T16:14:21","witness":"initminer","transaction_merkle_root":"0000000000000000000000000000000000000000","extensions":[],"witness_signature":"2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e","transactions":[],"block_id":"000000b13707dfaad7c2452294d4cfa7c2098db4","signing_key":"STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX","transaction_ids":[]}},{"id":2,"result":{"previous":"000000b0c668dad57f55172da54899754aeba74b","timestamp":"2016-03-24T16:14:21","witness":"initminer","transaction_merkle_root":"0000000000000000000000000000000000000000","extensions":[],"witness_signature":"2036fd4ff7838ba32d6d27637576e1b1e82fd2858ac97e6e65b7451275218cbd2b64411b0a5d74edbde790c17ef704b8ce5d9de268cb43783b499284c77f7d9f5e","transactions":[],"block_id":"000000b13707dfaad7c2452294d4cfa7c2098db4","signing_key":"STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX","transaction_ids":[]}}]
'''


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
    # pylint: disable=too-many-arguments

    def __init__(self,
                 url=None,
                 num_pools=2,
                 max_size=10,
                 timeout=60,
                 retries=30,
                 pool_block=False,
                 tcp_keepalive=True,
                 **kwargs):
        url = url or os.environ.get('STEEMD_HTTP_URL',
                                    'https://steemd.steemitdev.com')
        self.url = url
        self.hostname = urlparse(url).hostname
        self.return_with_args = kwargs.get('return_with_args', False)
        self.re_raise = kwargs.get('re_raise', False)
        self.max_workers = kwargs.get('max_workers', None)

        maxsize = max_size
        timeout = timeout
        retries = retries
        pool_block = pool_block
        tcp_keepalive = tcp_keepalive

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
    def json_rpc_body(name, *args, as_json=True, _id=None):
        _id = _id or int(time.time() * 1000000)
        body_dict = {"method": name, "params": args,
                     "jsonrpc": "2.0", "id": _id}
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

    def test_batch_support(self, url):
        batch_request = '[{"id":1,"jsonrpc":"2.0","method":"get_block","params":[1]},{"id":2,"jsonrpc":"2.0","method":"get_block","params":[1]}]'
        try:
            response = self.request(body=batch_request)
            return response.data.decode() == CORRECT_BATCH_TEST_RESPONSE
        except Exception as e:
            logger.error(e)
        return False

    get_block = partialmethod(exec, 'get_block')
