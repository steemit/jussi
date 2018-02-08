# -*- coding: utf-8 -*-
from jussi.cache.utils import jsonrpc_cache_key


def test_cache_key(urn_test_requests):
    jsonrpc_request, urn, url, ttl, timeout, jussi_request = urn_test_requests
    result = jsonrpc_cache_key(jussi_request)
    assert result == urn
