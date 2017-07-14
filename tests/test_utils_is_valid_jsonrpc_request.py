# -*- coding: utf-8 -*-
import jussi.utils
import pytest


def test_doesnt_assert_good_requests(all_steemd_jrpc_calls):
    jussi.utils.is_valid_jsonrpc_request(all_steemd_jrpc_calls)


def test_raises_bad_requests(invalid_jrpc_requests):
    with pytest.raises(AssertionError):
        jussi.utils.is_valid_jsonrpc_request(invalid_jrpc_requests)
