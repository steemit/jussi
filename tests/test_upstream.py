# -*- coding: utf-8 -*-
import os

from .conftest import TEST_UPSTREAM_CONFIG

from jussi.upstream import Upstream
from jussi.upstream import _Upstreams
from jussi.urn import URN
from jussi.urn import from_request


def test_upstream_url(urn_test_request_dict):
    os.environ['JUSSI_ACCOUNT_TRANSFER_STEEMD_URL'] = 'account_transfer_url'
    upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    test_urn = from_request(jsonrpc_request)
    upstream = Upstream.from_urn(test_urn, upstreams=upstreams)
    del os.environ['JUSSI_ACCOUNT_TRANSFER_STEEMD_URL']
    assert upstream.url == url


def test_upstream_ttl(urn_test_request_dict):
    upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    test_urn = from_request(jsonrpc_request)
    upstream = Upstream.from_urn(test_urn, upstreams=upstreams)
    assert upstream.ttl == ttl


def test_upstream_timeout(urn_test_request_dict):
    upstreams = _Upstreams(TEST_UPSTREAM_CONFIG, validate=False)
    jsonrpc_request, urn, url, ttl, timeout = urn_test_request_dict
    test_urn = from_request(jsonrpc_request)
    upstream = Upstream.from_urn(test_urn, upstreams=upstreams)
    assert upstream.timeout == timeout
