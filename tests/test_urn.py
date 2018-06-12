# -*- coding: utf-8 -*-

import pytest
from jussi.errors import InvalidNamespaceError
from jussi.errors import InvalidNamespaceAPIError
from jussi.urn import URN
from jussi.urn import from_request
from jussi.urn import _parse_jrpc


def test_parse_jrpc_namespaces(full_urn_test_request_dicts):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dicts
    result = _parse_jrpc(jsonrpc_request)
    assert result == urn_parsed


@pytest.mark.parametrize("jsonrpc_request,expected", [
    # unknown numeric api
    ({
        'id': 1,
        'jsonrpc': '2.0',
        'method': 'call',
        'params': [2, 'get_account_count', []]
    },
        InvalidNamespaceAPIError
    ),
    ({
        'id': 1,
        'jsonrpc': '2.0',
        'method': '.......',
        'params': [2, 'get_account_count', []]
    },
        InvalidNamespaceError
    ),

])
def test_parse_jrpc_errors(jsonrpc_request, expected):
    with pytest.raises(expected):
        result = _parse_jrpc(jsonrpc_request)


def test_parse_jrpc_namespace_is_steemd(just_steemd_requests_and_responses):
    req, resp = just_steemd_requests_and_responses
    result = _parse_jrpc(req)
    assert result['namespace'] == 'steemd'


def test_parse_jrpc_namespace_is_appbase(appbase_requests_and_responses):
    req, resp = appbase_requests_and_responses
    result = _parse_jrpc(req)
    assert result['namespace'] == 'appbase'


def test_urn_str(full_urn_test_request_dicts):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dicts
    result_urn = from_request(jsonrpc_request)
    assert str(result_urn) == urn


def test_urn_hash(full_urn_test_request_dicts):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dicts
    result_urn = from_request(jsonrpc_request)
    assert hash(result_urn) == hash(urn)


def test_urn_eq(full_urn_test_request_dicts):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dicts
    result_urn = from_request(jsonrpc_request)
    assert result_urn == urn


def test_urn_not_eq(full_urn_test_request_dicts):
    jsonrpc_request, urn_parsed, urn, url, ttl, timeout = full_urn_test_request_dicts
    result_urn = from_request(jsonrpc_request)
    assert result_urn != 'nope'
