# -*- coding: utf-8 -*-
import sanic.response

from jussi.middlewares.jussi import finalize_jussi_response
from jussi.upstream import _Upstreams
from jussi.request.http import HTTPRequest
from .conftest import TEST_UPSTREAM_CONFIG


req = {"id": "1", "jsonrpc": "2.0",
       "method": "get_block", "params": [1000]}
response = {
    "id": 1,
    "result": {
        "previous": "000003e7c4fd3221cf407efcf7c1730e2ca54b05",
        "timestamp": "2016-03-24T16:55:30",
        "witness": "initminer",
        "transaction_merkle_root": "0000000000000000000000000000000000000000",
        "extensions": [],
        "witness_signature": "207f15578cac20ac0e8af1ebb8f463106b8849577e21cca9fc60da146d1d95df88072dedc6ffb7f7f44a9185bbf9bf8139a5b4285c9f423843720296a44d428856",
        "transactions": [],
        "block_id": "000003e8b922f4906a45af8e99d86b3511acd7a5",
        "signing_key": "STM8GC13uCZbP44HzMLV6zPZGwVQ8Nt4Kji8PapsPiNq1BK153XTX",
        "transaction_ids": []}}


def test_request_id_in_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.post('/post')
    def handler(r):
        return sanic.response.text('post')

    @app.get('/get')
    def handler(r):
        return sanic.response.text('get')

    @app.head('/head')
    def handler(r):
        return sanic.response.text('head')

    @app.options('/options')
    def handler(r):
        return sanic.response.text('options')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.get('/get')
    assert 'x-jussi-request-id' in response.headers

    _, response = app.test_client.post('/post')
    assert 'x-jussi-request-id' in response.headers

    _, response = app.test_client.head('/head')
    assert 'x-jussi-request-id' in response.headers

    _, response = app.test_client.options('/options')
    assert 'x-jussi-request-id' in response.headers


def test_jussi_request_ids_equal():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.post('/post')
    def handler(r):
        return sanic.response.text('post')

    @app.get('/get')
    def handler(r):
        return sanic.response.text('get')

    @app.head('/head')
    def handler(r):
        return sanic.response.text('head')

    @app.options('/options')
    def handler(r):
        return sanic.response.text('options')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.get('/get',
                                      headers={
                                          'x-jussi-request-id': '123456789012345'
                                      })
    assert response.headers['x-jussi-request-id'] == '123456789012345'

    _, response = app.test_client.post('/post',
                                       headers={
                                           'x-jussi-request-id': '123456789012345'
                                       })
    assert response.headers['x-jussi-request-id'] == '123456789012345'

    _, response = app.test_client.head('/head',
                                       headers={
                                           'x-jussi-request-id': '123456789012345'
                                       })
    assert response.headers['x-jussi-request-id'] == '123456789012345'

    _, response = app.test_client.options('/options',
                                          headers={
                                              'x-jussi-request-id': '123456789012345'
                                          })
    assert response.headers['x-jussi-request-id'] == '123456789012345'


def test_response_time_in_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.post('/post')
    def handler(r):
        return sanic.response.text('post')

    @app.get('/get')
    def handler(r):
        return sanic.response.text('get')

    @app.head('/head')
    def handler(r):
        return sanic.response.text('head')

    @app.options('/options')
    def handler(r):
        return sanic.response.text('options')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)
    _, response = app.test_client.post('/post')

    assert 'x-jussi-response-time' in response.headers
    assert float(response.headers['x-jussi-response-time']) > 0

    _, response = app.test_client.get('/get')
    assert 'x-jussi-response-time' in response.headers
    assert float(response.headers['x-jussi-response-time']) > 0

    _, response = app.test_client.head('/head')
    assert 'x-jussi-response-time' in response.headers
    assert float(response.headers['x-jussi-response-time']) > 0

    _, response = app.test_client.options('/options')
    assert 'x-jussi-response-time' in response.headers
    assert float(response.headers['x-jussi-response-time']) > 0


def test_urn_parts_in_post_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.post('/post')
    def handler(r):
        _ = r.jsonrpc  # trigger lazy parsing
        return sanic.response.text('post')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.post('/post', json=req)
    assert 'x-jussi-request-id' in response.headers
    assert response.headers['x-jussi-namespace'] == 'steemd', f'{response.headers}'
    assert response.headers['x-jussi-api'] == 'database_api', f'{response.headers}'
    assert response.headers['x-jussi-method'] == 'get_block', f'{response.headers}'
    assert response.headers['x-jussi-params'] == '[1000]', f'{response.headers}'


def test_urn_parts_not_in_batch_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.post('/post')
    def handler(r):
        _ = r.jsonrpc  # trigger lazy parsing
        return sanic.response.text('post')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.post('/post', json=[req, req])
    assert 'x-jussi-request-namespace' not in response.headers
    assert 'x-jussi-request-api' not in response.headers
    assert 'x-jussi-request-method' not in response.headers
    assert 'x-jussi-request-params' not in response.headers


def test_urn_parts_not_in_get_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.get('/get')
    def handler(r):
        _ = r.jsonrpc  # trigger lazy parsing
        return sanic.response.text('get')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.get('/get')
    assert 'x-jussi-request-namespace' not in response.headers
    assert 'x-jussi-request-api' not in response.headers
    assert 'x-jussi-request-method' not in response.headers
    assert 'x-jussi-request-params' not in response.headers


def test_urn_parts_not_in_head_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.head('/head')
    def handler(r):
        _ = r.jsonrpc  # trigger lazy parsing
        return sanic.response.text('head')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.head('/head')
    assert 'x-jussi-request-namespace' not in response.headers
    assert 'x-jussi-request-api' not in response.headers
    assert 'x-jussi-request-method' not in response.headers
    assert 'x-jussi-request-params' not in response.headers


def test_urn_parts_not_in_options_response_headers():
    app = sanic.Sanic('testApp', request_class=HTTPRequest)

    @app.options('/options')
    def handler(r):
        _ = r.jsonrpc  # trigger lazy parsing
        return sanic.response.text('options')

    app.config.upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    app.response_middleware.append(finalize_jussi_response)

    _, response = app.test_client.options('/options')
    assert 'x-jussi-request-namespace' not in response.headers
    assert 'x-jussi-request-api' not in response.headers
    assert 'x-jussi-request-method' not in response.headers
    assert 'x-jussi-request-params' not in response.headers
