# -*- coding: utf-8 -*-
import sanic
import sanic.response

import pytest
from jussi.errors import InvalidRequest
from jussi.errors import JsonRpcError
from jussi.errors import ParseError
from jussi.errors import ServerError
from jussi.errors import handle_middleware_exceptions


class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class MockRequest(AttrDict):
    def __init__(self,
                 body=None,
                 path=None,
                 headers=None,
                 version=None,
                 method=None,
                 transport=None,
                 text=None,
                 json=None, **kwargs):
        super().__init__()
        self.body = body or 'body'
        self.path = path or 'path'
        self.headers = headers or {
            'X-Amzn-Trace-Id': 'amzn_trace_id',
            'X-Amzn-RequestId': 'amzn_request_id',
            'x-jussi-request-id': 'jussi_request_id'
        }
        self.version = version or '1.1'
        self.method = method or 'POST'
        self.transport = transport
        self.text = text or ''
        self.json = json or ''
        for k, v in kwargs:
            self.k = v


jrpc_req = {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'yo.test_method',
    'params': [1, 2, 3]
}


default_error_message_body_data = {
    'body': jrpc_req,
    'is_batch': False,
    'batch_request_count': None
}

default_error_message_data = {
    'error_id': '123',
    'request': {
                'method': 'POST',
                'path': 'path',
                'body': default_error_message_body_data,
                'amzn_trace_id': 'amzn_trace_id',
                'amzn_request_id': 'amzn_request_id',
                'jussi_request_id': 'jussi_request_id'
    }
}


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


test_data = ['a', 1, 2, 'b', 'c', [], 'd', {}]

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
                'path': 'path',
                'body': default_error_message_body_data,
                'amzn_trace_id': 'amzn_trace_id',
                'amzn_request_id': 'amzn_request_id',
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
      {'id': 1, 'jsonrpc': '2.0',
       'error':
       {'code': -32603, 'message': 'Internal Error',
        'data': {'request': None, 'error_id': '123'}}}),
     ({'jsonrpc': '2.0', 'method': 'yo.test_method'},
      Exception(),
      {'jsonrpc': '2.0',
       'error':
       {'code': -32603, 'message': 'Internal Error',
        'data': {'request': None, 'error_id': '123'}}}),
     (jrpc_req,
      JsonRpcError(
          sanic_request=MockRequest(json=jrpc_req),
          error_id='123'),
      jrpc_error),
     (jrpc_req,
      JsonRpcError(
          sanic_request=MockRequest(json=jrpc_req),
          data=test_data, error_id='123'),
      jrpc_error_with_data),
     (jrpc_req,
      JsonRpcError(
          sanic_request=MockRequest(json=jrpc_req),
          data=test_data, exception=Exception('test'),
          error_id='123'),
      jrpc_error_with_data),
     (jrpc_req,
      ParseError(
          sanic_request=MockRequest(json=jrpc_req),
          error_id='123'),
      parse_error),
     (jrpc_req,
      InvalidRequest(
          sanic_request=MockRequest(json=jrpc_req),
          error_id='123'),
      invalid_request_error),
     (jrpc_req,
      ServerError(
          sanic_request=MockRequest(json=jrpc_req),
          error_id='123'),
      server_error), ])
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
