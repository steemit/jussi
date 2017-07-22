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



jrpc_req = {
    'id': 1,
    'jsonrpc': '2.0',
    'method': 'yo.test_method',
    'params': [1, 2, 3]
}

jrpc_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'message':
            'Internal Error'
    }
}


test_data = ['a',1,2,'b','c',[],'d',{}]

jrpc_error_with_data = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32603,
        'data': test_data,
        'message':
            'Internal Error'
    }
}


parse_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32700,
        'message':
            'Parse error'
    }
}

invalid_request_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32600,
        'message':
            'Invalid Request'
    }
}

server_error = {
    'id': 1,
    'jsonrpc': '2.0',
    'error': {
        'code': -32000,
        'message':
            'Server error'
    }
}


@pytest.mark.test_app
@pytest.mark.parametrize('rpc_req,error,expected', [
    (jrpc_req,
     Exception(),
     jrpc_error
     ),
    (
        {'jsonrpc': '2.0', 'method': 'yo.test_method'},
        Exception(),
        {'jsonrpc': '2.0','error': {'code': -32603,'message':'Internal Error'}}
    ),
    (
        jrpc_req,
        JsonRpcError(sanic_request=AttrDict(json=jrpc_req)),
        jrpc_error
    ),
    (
        jrpc_req,
        JsonRpcError(sanic_request=AttrDict(json=jrpc_req),data=test_data),
        jrpc_error_with_data
    ),
    (
        jrpc_req,
        JsonRpcError(sanic_request=AttrDict(json=jrpc_req), data=test_data, exception=Exception('test')),
        jrpc_error_with_data
    ),
    (
        jrpc_req,
        ParseError(sanic_request=AttrDict(json=jrpc_req)),
        parse_error
    ),
(
        jrpc_req,
        InvalidRequest(sanic_request=AttrDict(json=jrpc_req)),
        invalid_request_error
    ),
(
        jrpc_req,
        ServerError(sanic_request=AttrDict(json=jrpc_req)),
        server_error
    ),

])
def test_middleware_error_handler(loop, rpc_req, error, expected):
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
    response_json = loop.run_until_complete(response.json())
    assert response_json == expected
