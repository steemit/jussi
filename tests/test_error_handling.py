# -*- coding: utf-8 -*-
import pytest
import sanic
import sanic.response
import sanic.request
import ujson
from jussi.errors import InvalidRequest
from jussi.errors import JsonRpcError
from jussi.errors import ParseError
from jussi.errors import ServerError
from jussi.errors import handle_middleware_exceptions


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def make_fake_request(
        body=None,
        path=None,
        headers=None,
        version='1.1',
        method='POST',
        transport=None):

    body = body or 'body'

    path = path or '/path'

    url = 'http://localhost' + path
    url_bytes = url.encode()
    if isinstance(body, dict):
        body = ujson.dumps(body)

    headers = headers or {
        'X-Amzn-Trace-Id': 'amzn_trace_id',
        'x-jussi-request-id': 'jussi_request_id'
    }

    req = sanic.request.Request(
        url_bytes=url_bytes, headers=headers, version=version, method=method,
        transport=transport)
    req.body = body
    return req


jrpc_req = {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'yo.test_method',
    'params': [1, 2, 3]
}

fake_sanic_request = make_fake_request(body=jrpc_req)

fake_minimal_sanic_request = make_fake_request(path='/', headers={})

default_error_message_body_data = {
    'body': jrpc_req,
    'is_batch': False,
    'batch_request_count': None
}

default_error_message_data = {
    'error_id': '123',
    'request': {
        'method': 'POST',
        'path': '/path',
        'body': default_error_message_body_data,
        'amzn_trace_id': 'amzn_trace_id',
        'jussi_request_id': 'jussi_request_id'
    }
}

minimal_error0 = {
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'request': {
                'method': 'POST',
                'path': '/',
                'body': {
                    'body': {
                        'id': 1,
                        'jsonrpc': '2.0',
                        'method': 'yo.test_method',
                        'params': [
                            1,
                            2,
                            3]},
                    'is_batch': False,
                    'batch_request_count': None},
                'amzn_trace_id': None,

                'jussi_request_id': None}}},
    'id': 1}

minimal_error = {
    'jsonrpc': '2.0',
    'error':
    {'code': -32603, 'message': 'Internal Error',
     'data':
     {'error_id': '123',
      'request':
      {'method': 'POST', 'path': '/',
       'body':
       {'body': {'jsonrpc': '2.0', 'method': 'yo.test_method'},
        'is_batch': False, 'batch_request_count': None},
       'amzn_trace_id': None,
       'jussi_request_id': None}}}}
minimal_error2 = {
    'jsonrpc': '2.0',
    'error':
    {'code': -32603, 'message': 'Internal Error',
     'data':
     {'error_id': '123',
      'request':
      {'method': 'POST', 'path': '/path',
       'body':
       {
           'body':
           {'id': 1, 'jsonrpc': '2.0', 'method': 'yo.test_method',
            'params': [1, 2, 3]},
           'is_batch': False, 'batch_request_count': None},
       'amzn_trace_id': 'amzn_trace_id',
       'jussi_request_id': 'jussi_request_id'}}},
    'id': 1}


jrpc_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message':
        'Internal Error',
        'data': default_error_message_data
    }
}


test_data = dict(a=1, b=2, c=3, d={})

jrpc_error_with_data = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message':
        'Internal Error',
        'data': {
            'error_id': '123',
            'request': {
                'method': 'POST',
                'path': '/path',
                'body': default_error_message_body_data,
                'amzn_trace_id': 'amzn_trace_id',
                'jussi_request_id': 'jussi_request_id'
            },
            'data': test_data
        }

    }
}

parse_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32700,
        'message':
        'Parse error',
        'data': default_error_message_data
    }
}

invalid_request_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32600,
        'message': 'Invalid Request',
        'data': default_error_message_data
    }
}

server_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32000,
        'message': 'Server error',
        'data': default_error_message_data
    }
}


@pytest.mark.test_app
@pytest.mark.parametrize(
    'rpc_req,error,expected',
    [(jrpc_req, Exception(),
      minimal_error0),
     ({'jsonrpc': '2.0', 'method': 'yo.test_method'},
      Exception(),
      minimal_error),
     (jrpc_req,
      JsonRpcError(sanic_request=fake_sanic_request, error_id='123'),
      minimal_error2),
     (jrpc_req,
      JsonRpcError(
          sanic_request=fake_sanic_request, data=test_data, error_id='123'),
      jrpc_error_with_data),
     (jrpc_req,
      JsonRpcError(
          sanic_request=fake_sanic_request, data=test_data,
          exception=Exception('test'),
          error_id='123'),
      jrpc_error_with_data),
     (jrpc_req,
      ParseError(sanic_request=fake_sanic_request, error_id='123'),
      parse_error),
     (jrpc_req,
      InvalidRequest(sanic_request=fake_sanic_request, error_id='123'),
      invalid_request_error),
     (jrpc_req,
      ServerError(sanic_request=fake_sanic_request, error_id='123'),
      server_error)])
def test_middleware_error_handler(rpc_req, error, expected):
    app = sanic.Sanic('test_text')

    # pylint: disable=unused-argument,unused-variable

    @app.post('/')
    def handler(request):
        return sanic.response.text('Hello')

    @app.middleware('request')
    @handle_middleware_exceptions
    async def error_middleware(request):
        raise error

    req, response = app.test_client.post('/', json=rpc_req)
    assert response.headers['Content-Type'] == 'application/json'
    assert response.status == 200
    if response.json['error']['data']['error_id'] != '123':
        response.json['error']['data']['error_id'] = '123'
    assert response.json == expected
