# -*- coding: utf-8 -*-
import pytest
import sanic
import sanic.response
import sanic.request
from jussi.errors import InvalidRequest
from jussi.errors import JsonRpcError
from jussi.errors import ParseError
from jussi.errors import ServerError
from jussi.errors import handle_middleware_exceptions
from .conftest import make_request

from jussi.request.http import HTTPRequest


jrpc_req = {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'yo.test_method',
    'params': [1, 2, 3]
}

fake_http_request = make_request(body=jrpc_req)

fake_minimal_http_request = make_request()


default_error_message_data = {
    'error_id': '123',
    'jussi_request_id': '123'
}

minimal_error0 = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'jussi_request_id': '123'
        }
    }
}

minimal_error_with_no_jsonrpc_id = {
    'id': None,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'jussi_request_id': '123'
        }
    }
}

minimal_error2 = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'jussi_request_id': '123'
        }
    }
}


jrpc_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'jussi_request_id': '123'
        }
    }
}


test_data = dict(a=1, b=2, c=3, d={})

jrpc_error_with_data = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message': 'Internal Error',
        'data': {
            'error_id': '123',
            'jussi_request_id': '123'
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
      minimal_error_with_no_jsonrpc_id),
     (jrpc_req,
      JsonRpcError(http_request=fake_http_request),
      minimal_error2),
     (jrpc_req,
      JsonRpcError(
          http_request=fake_http_request, data=test_data),
      jrpc_error_with_data),
     (jrpc_req,
      JsonRpcError(
          http_request=fake_http_request, data=test_data,
          exception=Exception('test'),
          error_id='123'),
      jrpc_error_with_data),
     (jrpc_req,
      ParseError(http_request=fake_http_request),
      parse_error),
     (jrpc_req,
      InvalidRequest(http_request=fake_http_request),
      invalid_request_error),
     (jrpc_req,
      ServerError(http_request=fake_http_request),
      server_error)])
def test_middleware_error_handler(rpc_req, error, expected):
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    # pylint: disable=unused-argument,unused-variable

    @app.post('/')
    def handler(request):
        return sanic.response.text('Hello')

    @app.middleware('request')
    @handle_middleware_exceptions
    async def error_middleware(request):
        raise error

    req, response = app.test_client.post('/', json=rpc_req, headers={'x-jussi-request-id': '123'})
    assert response.headers['Content-Type'] == 'application/json'
    assert response.status == 200
    if response.json['error']['data']['error_id'] != '123':
        response.json['error']['data']['error_id'] = '123'
    assert response.json == expected
