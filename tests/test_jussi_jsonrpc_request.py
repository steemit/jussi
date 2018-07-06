# -*- coding: utf-8 -*-
import os
from copy import deepcopy
import ujson

from jussi.upstream import _Upstreams
from jussi.request.jsonrpc import JSONRPCRequest

from .conftest import TEST_UPSTREAM_CONFIG
from .conftest import AttrDict
from .conftest import make_request
from jussi.request.jsonrpc import _empty
from jussi.request.jsonrpc import from_http_request as jsonrpc_from_request


def test_request_id(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.id == jsonrpc_request.get('id')


def test_request_jsonrpc(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.jsonrpc == '2.0'


def test_request_method(full_urn_test_request_dict):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.method == jsonrpc_request['method']


def test_request_params(full_urn_test_request_dict):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.params == jsonrpc_request.get('params', _empty)


def test_request_urn(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.urn == urn


def test_request_upstream(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    os.environ['JUSSI_ACCOUNT_TRANSFER_STEEMD_URL'] = 'account_transfer_url'
    assert jussi_request.upstream.url == url


def test_request_batch_index(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.batch_index == 0
    jussi_request = jsonrpc_from_request(dummy_request, 1, jsonrpc_request)
    assert jussi_request.batch_index == 1


def test_request_to_dict(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.to_dict() == jsonrpc_request


def test_request_to_json(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert ujson.loads(jussi_request.json()) == jussi_request.to_dict()


def test_upstream_id(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.upstream_id == 123

    jussi_request = jsonrpc_from_request(dummy_request, 1, jsonrpc_request)
    assert jussi_request.upstream_id == 124


def test_upstream_headers(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.upstream_headers == {
        'x-jussi-request-id': '123',
        'x-amzn-trace-id': '123'}

    dummy_request.headers['x-amzn-trace-id'] = '1'
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)
    assert jussi_request.upstream_headers == {
        'x-jussi-request-id': '123',
        'x-amzn-trace-id': '1'
    }


def upstream_request(urn_test_request_dict):
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    dummy_request = make_request()
    jussi_request = jsonrpc_from_request(dummy_request, 0, jsonrpc_request)

    cpy = deepcopy(jussi_request)
    cpy['id'] = 123456789012345
    assert jussi_request.to_upstream_request(as_json=False) == cpy
    assert jussi_request.to_upstream_request() == ujson.dumps(cpy,
                                                              ensure_ascii=False)

    cpy = deepcopy(jussi_request)
    cpy['id'] = 123456789012346
    jussi_request = jsonrpc_from_request(dummy_request, 1, cpy)
    assert jussi_request.to_upstream_request(as_json=False) == cpy
    assert jussi_request.to_upstream_request() == ujson.dumps(cpy,
                                                              ensure_ascii=False)


def test_log_extra():
    # TODO
    pass


def test_request_hash():
    # TODO
    pass
